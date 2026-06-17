import os
import httpx
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Header, Footer, ListView, ListItem, Label, Static, Input
from textual.worker import Worker

PINNED_USER = "larprxlokm"
CURATED_PROJECTS = [
    {"name": "linux", "owner": "torvalds"},
    {"name": "textual", "owner": "textualize"},
    {"name": "cpython", "owner": "python"},
    {"name": "rust", "owner": "rust-lang"}
]

HTTP_CLIENT = httpx.AsyncClient(
    follow_redirects=True,
    timeout=httpx.Timeout(5.0, connect=2.0),
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
)

class mGit(App):
    CSS = """
    Screen {
        background: #1e1e1e;
    }
    Horizontal {
        height: 100%;
    }
    #sidebar-container {
        width: 35%;
        border-right: tall #333333;
        background: #161616;
    }
    #search-input {
        background: #222222;
        border: none;
        color: #ffffff;
        margin: 1 1 0 1;
    }
    #sidebar {
        height: 100%;
        background: transparent;
    }
    #main-content {
        width: 65%;
        padding: 1 2;
    }
    #repo-details {
        height: auto;
        margin-bottom: 1;
    }
    #readme-container {
        height: 1fr;
        border-top: solid #333333;
        padding-top: 1;
        overflow-y: scroll;
    }
    #readme-content {
        height: auto;
    }
    """
    
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "download_repo", "Download ZIP"),
        ("f", "focus_search", "Search"),
        ("h", "load_home", "Home / Pins"),
    ]

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
        yield Footer()

    def on_mount(self) -> None:
        self.title = "mGit"
        self.action_load_home()

    def action_focus_search(self) -> None:
        self.query_one("#search-input", Input).focus()

    def action_load_home(self) -> None:
        sidebar = self.query_one("#sidebar", ListView)
        sidebar.clear()
        
        item = ListItem(Label(f"Profile: {PINNED_USER}"))
        item.is_profile_link = True
        item.username = PINNED_USER
        sidebar.append(item)
        
        sidebar.append(ListItem(Label("───────────────────")))
        
        for project in CURATED_PROJECTS:
            item = ListItem(Label(f"Repo: {project['owner']}/{project['name']}"))
            item.is_direct_repo = True
            item.repo_owner = project['owner']
            item.repo_name = project['name']
            sidebar.append(item)

        self.query_one("#repo-details", Static).update(
            "[#00ffcc][b]Welcome to mGit[/b][/#00ffcc]\n\n"
            "• Use the sidebar to click pinned projects or your profile\n"
            "• Use the search bar to look up any other public GitHub user\n"
            "• Press [b]H[/b] at any time to return to this home view"
        )
        self.query_one("#readme-content", Static).update("")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        username = event.value.strip()
        if username:
            sidebar = self.query_one("#sidebar", ListView)
            sidebar.clear()
            sidebar.append(ListItem(Label("Searching...")))
            self.fetch_github_data(username)

    @work(exclusive=True)
    async def fetch_github_data(self, username: str) -> list:
        url = f"https://api.github.com/users/{username}/repos?sort=updated"
        headers = {"Accept": "application/vnd.github.v3+json"}
        response = await HTTP_CLIENT.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return [{"error": True, "message": "User not found"}]
        return [{"error": True, "message": f"Status {response.status_code}"}]

    @work(exclusive=True)
    async def fetch_single_repo_data(self, owner: str, name: str) -> dict:
        url = f"https://api.github.com/repos/{owner}/{name}"
        headers = {"Accept": "application/vnd.github.v3+json"}
        response = await HTTP_CLIENT.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        return {"error": True, "message": f"Status {response.status_code}"}

    @work(exclusive=True)
    async def fetch_readme(self, owner: str, name: str) -> str:
        url = f"https://api.github.com/repos/{owner}/{name}/readme"
        headers = {"Accept": "application/vnd.github.v3.raw"}
        response = await HTTP_CLIENT.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return "No README found or unable to fetch."

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.state == event.state.SUCCESS:
            result = event.worker.result
            
            if isinstance(result, str):
                self.query_one("#readme-content", Static).update(result)
                return

            if isinstance(result, dict) and "owner" in result:
                self.display_repo_details(result)
                return

            if isinstance(result, list):
                sidebar = self.query_one("#sidebar", ListView)
                sidebar.clear()
                
                if not result:
                    sidebar.append(ListItem(Label("No public repos")))
                    return

                if result[0].get("error"):
                    sidebar.append(ListItem(Label(result[0]["message"])))
                    return

                for repo in result:
                    item = ListItem(Label(repo.get("name", "Unknown")))
                    item.repo_data = repo
                    sidebar.append(item)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if hasattr(event.item, "is_profile_link"):
            sidebar = self.query_one("#sidebar", ListView)
            sidebar.clear()
            sidebar.append(ListItem(Label("Loading profile repos...")))
            self.fetch_github_data(event.item.username)
            return
            
        if hasattr(event.item, "is_direct_repo"):
            details_panel = self.query_one("#repo-details", Static)
            details_panel.update("[yellow]Loading project details...[/yellow]")
            self.query_one("#readme-content", Static).update("[yellow]Loading README...[/yellow]")
            self.fetch_single_repo_data(event.item.repo_owner, event.item.repo_name)
            self.fetch_readme(event.item.repo_owner, event.item.repo_name)
            return

        repo_data = getattr(event.item, "repo_data", None)
        if repo_data:
            self.display_repo_details(repo_data)
            self.query_one("#readme-content", Static).update("[yellow]Loading README...[/yellow]")
            self.fetch_readme(repo_data["owner"]["login"], repo_data["name"])

    def display_repo_details(self, repo_data: dict) -> None:
        self.active_repo_data = repo_data
        details_panel = self.query_one("#repo-details", Static)
        content = (
            f"[#00ffcc][b]{repo_data.get('full_name', repo_data.get('name'))}[/b][/#00ffcc]\n"
            f"[#888888]{repo_data.get('description') or 'No description.'}[/#888888]\n\n"
            f"Stars: {repo_data.get('stargazers_count')}  |  "
            f"Forks: {repo_data.get('forks_count')}  |  "
            f"Issues: {repo_data.get('open_issues_count')}\n"
            f"URL: {repo_data.get('html_url')}"
        )
        details_panel.update(content)

    def action_download_repo(self) -> None:
        repo_data = None
        sidebar = self.query_one("#sidebar", ListView)
        
        if sidebar.index is not None and sidebar.index < len(sidebar.children):
            selected_item = sidebar.children[sidebar.index]
            repo_data = getattr(selected_item, "repo_data", None)
            
        if not repo_data and hasattr(self, "active_repo_data"):
            repo_data = self.active_repo_data

        if repo_data:
            owner = repo_data["owner"]["login"]
            repo_name = repo_data["name"]
            details_panel = self.query_one("#repo-details", Static)
            details_panel.update("[yellow]Downloading repository archive...[/yellow]")
            self.download_archive(owner, repo_name)

    @work(exclusive=False)
    async def download_archive(self, owner: str, repo_name: str) -> None:
        url = f"https://api.github.com/repos/{owner}/{repo_name}/zipball"
        headers = {"Accept": "application/vnd.github.v3+json"}
        filename = f"{repo_name}.zip"
        
        response = await HTTP_CLIENT.get(url, headers=headers)
        if response.status_code == 200:
            with open(filename, "wb") as f:
                f.write(response.content)
            self.update_status(f"Downloaded successfully to {os.path.abspath(filename)}")
        else:
            self.update_status(f"Download failed with status {response.status_code}")

    def update_status(self, message: str) -> None:
        self.query_one("#repo-details", Static).update(message)

    async def action_quit(self) -> None:
        await HTTP_CLIENT.aclose()
        self.exit()

if __name__ == "__main__":
    app = mGit()
    app.run()
