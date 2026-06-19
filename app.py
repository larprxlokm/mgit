import os
import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, Input

PINNED_USER = "larprxlokm"
CURATED_PROJECTS = [
    {"name": "linux", "owner": "torvalds"},
    {"name": "textual", "owner": "textualize"},
    {"name": "cpython", "owner": "python"},
    {"name": "rust", "owner": "rust-lang"}
]

HTTP_CLIENT = httpx.AsyncClient(
    follow_redirects=True,
    timeout=httpx.Timeout(10.0, connect=3.0),
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
    headers={"User-Agent": "mGit-App"}
)

class mGit(App):
    CSS = """
    Horizontal {
        height: 100%;
    }
    #sidebar-container {
        width: 30%;
        border-right: tall $border;
        background: $panel;
    }
    #search-input {
        margin: 1 1 0 1;
    }
    #sidebar {
        height: 100%;
        background: transparent;
    }
    #main-content {
        width: 40%;
        padding: 1 2;
    }
    #repo-details {
        height: auto;
        margin-bottom: 1;
    }
    #readme-container {
        height: 1fr;
        padding-top: 1;
        border-top: solid $border;
        overflow-y: scroll;
    }
    #readme-content {
        height: auto;
    }
    #browser-container {
        width: 30%;
        border-left: tall $border;
        background: $panel;
        padding: 1;
    }
    #browser-title {
        height: auto;
        margin-bottom: 1;
        text-align: center;
    }
    #browser-list {
        height: 1fr;
        background: transparent;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "download_repo", "Download ZIP"),
        ("f", "focus_search", "Search"),
        ("h", "load_home", "Home / Pins"),
        ("r", "fetch_releases_view", "Releases"),
        ("b", "back_dir", "Back Dir"),
    ]

    def __init__(self):
        super().__init__()
        self.current_owner = ""
        self.current_repo = ""
        self.current_path = []
        self.active_repo_data = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="sidebar-container"):
                yield Input(placeholder="Search GitHub users...", id="search-input")
                yield ListView(id="sidebar")
            with Container(id="main-content"):
                yield Static("", id="repo-details")
                with Container(id="readme-container"):
                    yield Static("", id="readme-content")
            with Vertical(id="browser-container"):
                yield Static("Files & Releases", id="browser-title")
                yield ListView(id="browser-list")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "mGit"
        self.action_load_home()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_load_home(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        sidebar.clear()
        
        profile_item = ListItem(Label(f"Profile: {PINNED_USER}"))
        profile_item.is_profile_link = True
        profile_item.username = PINNED_USER
        sidebar.append(profile_item)
        
        sidebar.append(ListItem(Label("───────────────────")))
        
        for project in CURATED_PROJECTS:
            repo_item = ListItem(Label(f"Repo: {project['owner']}/{project['name']}"))
            repo_item.is_direct_repo = True
            repo_item.repo_owner = project['owner']
            repo_item.repo_name = project['name']
            sidebar.append(repo_item)

        welcome_message = (
            "[accent][b]Welcome to mGit[/b][/accent]\n\n"
            "• Use the sidebar to click pinned projects or your profile\n"
            "• Use the search bar to look up any other public GitHub user\n"
            "• Press [b]H[/b] at any time to return to this home view\n"
            "• Press [b]R[/b] to look up available project releases"
        )
        self.query_one("#repo-details", Static).update(welcome_message)
        self.query_one("#readme-content", Static).update("")
        self.query_one("#browser-list", ListView).clear()
        self.query_one("#browser-title", Static).update("Files & Releases")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        username = event.value.strip()
        if not username:
            return
        sidebar = self.query_one("#sidebar", ListView)
        sidebar.clear()
        sidebar.append(ListItem(Label("Searching...")))
        self.fetch_github_data(username)

    @work(exclusive=True, name="fetch_github_data")
    async def fetch_github_data(self, username: str) -> None:
        url = f"https://api.github.com/users/{username}/repos?sort=updated"
        headers = {"Accept": "application/vnd.github.v3+json"}
        sidebar = self.query_one("#sidebar", ListView)
        try:
            response = await HTTP_CLIENT.get(url, headers=headers)
            sidebar.clear()
            if response.status_code == 200:
                for repo in response.json():
                    item = ListItem(Label(repo.get("name", "Unknown")))
                    item.repo_data = repo
                    sidebar.append(item)
            elif response.status_code == 403:
                sidebar.append(ListItem(Label("GitHub Rate Limit Exceeded")))
            elif response.status_code == 404:
                sidebar.append(ListItem(Label("User not found")))
            else:
                sidebar.append(ListItem(Label(f"Status {response.status_code}")))
        except httpx.RequestError:
            sidebar.clear()
            sidebar.append(ListItem(Label("Network error fetching repos")))

    @work(exclusive=True, name="fetch_single_repo_data")
    async def fetch_single_repo_data(self, owner: str, name: str) -> None:
        url = f"https://api.github.com/repos/{owner}/{name}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        try:
            response = await HTTP_CLIENT.get(url, headers=headers)
            if response.status_code == 200:
                self.display_repo_details(response.json())
            else:
                self.query_one("#repo-details", Static).update(f"[red]Error loading details: Status {response.status_code}[/red]")
        except httpx.RequestError:
            self.query_one("#repo-details", Static).update("[red]Network error fetching repo data[/red]")

    @work(exclusive=True, name="fetch_readme")
    async def fetch_readme(self, owner: str, name: str) -> None:
        url = f"https://api.github.com/repos/{owner}/{name}/readme"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        try:
            response = await HTTP_CLIENT.get(url, headers=headers)
            readme_widget = self.query_one("#readme-content", Static)
            if response.status_code == 200:
                text = response.text
                if len(text) > 50000:
                    text = text[:50000] + "\n\n... [Truncated due to size] ..."
                readme_widget.update(text)
            elif response.status_code == 403:
                readme_widget.update("GitHub Rate Limit Exceeded. Cannot fetch README.")
            else:
                readme_widget.update("No README found or unable to fetch.")
        except httpx.RequestError:
            self.query_one("#readme-content", Static).update("Network error fetching README.")

    @work(exclusive=True, name="fetch_contents")
    async def fetch_contents(self, owner: str, name: str, path_segments: list) -> None:
        path_str = "/".join(path_segments)
        url = f"https://api.github.com/repos/{owner}/{name}/contents/{path_str}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        browser_list = self.query_one("#browser-list", ListView)
        try:
            response = await HTTP_CLIENT.get(url, headers=headers)
            browser_list.clear()
            if response.status_code == 200:
                path_header = "/" + "/".join(self.current_path)
                self.query_one("#browser-title", Static).update(f"[b]{path_header}[/b]")
                
                if self.current_path:
                    back_item = ListItem(Label("📁 .. [Back]"))
                    back_item.is_back = True
                    browser_list.append(back_item)
                    
                for item in response.json():
                    item_name = item.get("name", "")
                    if item.get("type") == "dir":
                        li = ListItem(Label(f"📁 {item_name}"))
                        li.is_dir = True
                        li.dir_name = item_name
                        browser_list.append(li)
                    else:
                        li = ListItem(Label(f"📄 {item_name}"))
                        li.is_file = True
                        li.download_url = item.get("download_url")
                        browser_list.append(li)
            else:
                self.query_one("#browser-title", Static).update("Notice")
                browser_list.append(ListItem(Label("Empty or unavailable directory")))
        except httpx.RequestError:
            browser_list.clear()
            self.query_one("#browser-title", Static).update("Notice")
            browser_list.append(ListItem(Label("Network error loading contents")))

    @work(exclusive=True, name="fetch_file_raw")
    async def fetch_file_raw(self, download_url: str) -> None:
        try:
            response = await HTTP_CLIENT.get(download_url)
            if response.status_code == 200:
                text = response.text
                if len(text) > 50000:
                    text = text[:50000] + "\n\n... [Truncated due to size] ..."
                self.query_one("#readme-content", Static).update(text)
            else:
                self.query_one("#readme-content", Static).update("Unable to display file.")
        except httpx.RequestError:
            self.query_one("#readme-content", Static).update("Network error loading file content.")

    @work(exclusive=True, name="fetch_releases")
    async def fetch_releases(self, owner: str, name: str) -> None:
        url = f"https://api.github.com/repos/{owner}/{name}/releases"
        headers = {"Accept": "application/vnd.github.v3+json"}
        browser_list = self.query_one("#browser-list", ListView)
        try:
            response = await HTTP_CLIENT.get(url, headers=headers)
            browser_list.clear()
            if response.status_code == 200 and response.json():
                self.query_one("#browser-title", Static).update("[accent][b]Releases[/b][/accent]")
                back_to_files = ListItem(Label("📁 [Back to Files]"))
                back_to_files.is_back_to_files = True
                browser_list.append(back_to_files)
                
                for release in response.json():
                    tag = release.get("tag_name", "Unknown")
                    for asset in release.get("assets", []):
                        asset_name = asset.get("name")
                        li = ListItem(Label(f"📦 {tag}: {asset_name}"))
                        li.is_asset = True
                        li.asset_url = asset.get("browser_download_url")
                        li.asset_name = asset_name
                        browser_list.append(li)
            else:
                self.query_one("#browser-title", Static).update("Notice")
                browser_list.append(ListItem(Label("No releases found")))
        except httpx.RequestError:
            browser_list.clear()
            self.query_one("#browser-title", Static).update("Notice")
            browser_list.append(ListItem(Label("Network error fetching releases")))

    def action_fetch_releases_view(self) -> None:
        if self.current_owner and self.current_repo:
            self.query_one("#browser-title", Static).update("[yellow]Fetching releases...[/yellow]")
            self.fetch_releases(self.current_owner, self.current_repo)

    def action_back_dir(self) -> None:
        if self.current_path:
            self.current_path.pop()
            self.query_one("#browser-title", Static).update("[yellow]Loading...[/yellow]")
            self.fetch_contents(self.current_owner, self.current_repo, self.current_path)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        src_id = event.list_view.id
        
        if src_id == "sidebar":
            if hasattr(event.item, "is_profile_link"):
                sidebar = self.query_one("#sidebar", ListView)
                sidebar.clear()
                sidebar.append(ListItem(Label("Loading profile repos...")))
                self.fetch_github_data(event.item.username)
                return
                
            if hasattr(event.item, "is_direct_repo"):
                self.current_owner = event.item.repo_owner
                self.current_repo = event.item.repo_name
                self.current_path = []
                self.query_one("#repo-details", Static).update("[yellow]Loading project details...[/yellow]")
                self.query_one("#readme-content", Static).update("[yellow]Loading README...[/yellow]")
                self.query_one("#browser-title", Static).update("[yellow]Loading...[/yellow]")
                self.fetch_single_repo_data(self.current_owner, self.current_repo)
                self.fetch_readme(self.current_owner, self.current_repo)
                self.fetch_contents(self.current_owner, self.current_repo, self.current_path)
                return

            repo_data = getattr(event.item, "repo_data", None)
            if repo_data:
                self.current_owner = repo_data["owner"]["login"]
                self.current_repo = repo_data["name"]
                self.current_path = []
                self.display_repo_details(repo_data)
                self.query_one("#readme-content", Static).update("[yellow]Loading README...[/yellow]")
                self.query_one("#browser-title", Static).update("[yellow]Loading...[/yellow]")
                self.fetch_readme(self.current_owner, self.current_repo)
                self.fetch_contents(self.current_owner, self.current_repo, self.current_path)
                
        elif src_id == "browser-list":
            if hasattr(event.item, "is_back"):
                self.action_back_dir()
            elif hasattr(event.item, "is_back_to_files"):
                self.query_one("#browser-title", Static).update("[yellow]Loading...[/yellow]")
                self.fetch_contents(self.current_owner, self.current_repo, self.current_path)
            elif hasattr(event.item, "is_dir"):
                self.current_path.append(event.item.dir_name)
                self.query_one("#browser-title", Static).update("[yellow]Loading...[/yellow]")
                self.fetch_contents(self.current_owner, self.current_repo, self.current_path)
            elif hasattr(event.item, "is_file"):
                if event.item.download_url:
                    self.query_one("#readme-content", Static).update("[yellow]Loading file content...[/yellow]")
                    self.fetch_file_raw(event.item.download_url)
            elif hasattr(event.item, "is_asset"):
                self.query_one("#repo-details", Static).update(f"[yellow]Downloading release asset: {event.item.asset_name}...[/yellow]")
                self.download_direct_file(event.item.asset_url, event.item.asset_name)

    def display_repo_details(self, repo_data: dict) -> None:
        self.active_repo_data = repo_data
        details_panel = self.query_one("#repo-details", Static)
        
        title = repo_data.get('full_name', repo_data.get('name'))
        description = repo_data.get('description') or 'No description.'
        stars = repo_data.get('stargazers_count')
        forks = repo_data.get('forks_count')
        issues = repo_data.get('open_issues_count')
        url = repo_data.get('html_url')
        
        content = (
            f"[accent][b]{title}[/b][/accent]\n"
            f"[#888888]{description}[/#888888]\n\n"
            f"Stars: {stars}  |  "
            f"Forks: {forks}  |  "
            f"Issues: {issues}\n"
            f"URL: {url}"
        )
        details_panel.update(content)

    def action_download_repo(self) -> None:
        repo_data = getattr(self, "active_repo_data", None)
        if repo_data:
            owner = repo_data["owner"]["login"]
            repo_name = repo_data["name"]
            self.query_one("#repo-details", Static).update("[yellow]Downloading repository archive...[/yellow]")
            self.download_archive(owner, repo_name)

    @work(exclusive=False)
    async def download_archive(self, owner: str, repo_name: str) -> None:
        url = f"https://api.github.com/repos/{owner}/{repo_name}/zipball"
        headers = {"Accept": "application/vnd.github.v3+json"}
        filename = f"{repo_name}.zip"
        try:
            download_timeout = httpx.Timeout(300.0, connect=10.0)
            async with HTTP_CLIENT.stream("GET", url, headers=headers, timeout=download_timeout) as response:
                if response.status_code == 200:
                    with open(filename, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                    self.update_status(f"Downloaded successfully to {os.path.abspath(filename)}")
                else:
                    self.update_status(f"Download failed with status {response.status_code}")
        except Exception:
            self.update_status("Download failed: Connection timed out or reset.")

    @work(exclusive=False)
    async def download_direct_file(self, url: str, filename: str) -> None:
        try:
            download_timeout = httpx.Timeout(600.0, connect=15.0)
            async with HTTP_CLIENT.stream("GET", url, timeout=download_timeout) as response:
                if response.status_code == 200:
                    with open(filename, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                    self.update_status(f"Asset downloaded successfully to {os.path.abspath(filename)}")
                else:
                    self.update_status(f"Asset download failed with status {response.status_code}")
        except Exception:
            self.update_status("Asset download failed due to a network error.")

    def update_status(self, message: str) -> None:
        self.query_one("#repo-details", Static).update(message)

    async def action_quit(self) -> None:
        await HTTP_CLIENT.aclose()
        self.exit()

if __name__ == "__main__":
    app = mGit()
    app.run()
