import sys
import os
from livereload import Server


md_file = ""
html_file = ""
footer_file = "resources/footer_dev.html"

def md_to_html():
    global md_file
    global html_file
    global footer_file

    # Read the contents of the markdown file
    with open(md_file, "r", encoding="utf-8") as f:
        content = f.read()

    with open("resources/header.html", "r") as f:
        header = f.read()

    with open(footer_file, "r") as f:
        footer = f.read()

    content = f"{header}\n\n{content}\n\n{footer}"

    # Create the new HTML file
    html_file = md_file.replace(".md", ".html")
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(content)


def start_server():
    global md_file
    global html_file
    md_to_html()
    server = Server()
    server.watch(md_file, md_to_html)
    server.watch(html_file)
    server.serve(default_filename=html_file, root=f"./", liveport=35729, restart_delay=0)


def main():
    global md_file
    if not md_file.endswith(".md"):
        print("Error: The input file must be a markdown (.md) file.")
        return

    if not os.path.isfile(md_file):
        print(f"Error: The file '{md_file}' does not exist.")
        return

    start_server()


if __name__ == "__main__":
    if len(sys.argv) == 2 or len(sys.argv) == 3:
        md_file = sys.argv[1]
        if len(sys.argv) == 3 and sys.argv[2] == "release":
            footer_file = "resources/footer.html"
            md_to_html()
        else:
            main()
    else:
        print("Usage: python md_to_html.py <file.md>")
