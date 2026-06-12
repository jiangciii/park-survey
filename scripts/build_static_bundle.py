import argparse
import shutil
from pathlib import Path


def write_runtime_config(
    target: Path,
    api_base_url: str,
    public_base_url: str,
    survey_path: str,
    admin_login_path: str,
    static_mode: bool,
):
    content = (
        "window.__SURVEY_RUNTIME__ = Object.assign({}, window.__SURVEY_RUNTIME__ || {}, "
        "{"
        f'apiBaseUrl: "{api_base_url}", '
        f'publicBaseUrl: "{public_base_url}", '
        f'surveyPath: "{survey_path}", '
        f'adminLoginPath: "{admin_login_path}", '
        f"staticMode: {str(static_mode).lower()}, "
        f'submitMode: "{ "download" if static_mode else "api" }"'
        "});\n"
    )
    target.write_text(content, encoding="utf-8")


def copy_tree(src: Path, dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def adapt_html_paths(html: str, asset_prefix: str, static_prefix: str) -> str:
    return (
        html
        .replace("/assets/", asset_prefix)
        .replace("/static/", static_prefix)
    )


def write_cloudbase_bundle(root: Path, output: Path, api_base_url: str, public_base_url: str):
    survey_dir = output / "survey"
    static_dir = output / "static"
    assets_dir = output / "assets"

    survey_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(root / "survey_web.html", survey_dir / "index.html")
    shutil.copy2(root / "survey_app.js", static_dir / "survey_app.js")
    write_runtime_config(
        static_dir / "runtime-config.js",
        api_base_url.rstrip("/"),
        public_base_url.rstrip("/"),
        "/survey",
        "/admin/login",
        False,
    )

    copy_tree(root / "assets", assets_dir)

    (output / "index.html").write_text(
        """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta http-equiv="refresh" content="0; url=/survey/" />
  <title>城市公园使用体验调研</title>
</head>
<body>
  <p>正在跳转到问卷入口：<a href="/survey/">/survey/</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )


def write_github_pages_bundle(root: Path, output: Path, public_base_url: str):
    static_dir = output / "static"
    assets_dir = output / "assets"
    survey_dir = output / "survey"

    static_dir.mkdir(parents=True, exist_ok=True)
    survey_dir.mkdir(parents=True, exist_ok=True)

    html = (root / "survey_web.html").read_text(encoding="utf-8")
    (output / "index.html").write_text(
        adapt_html_paths(html, "assets/", "static/"),
        encoding="utf-8",
    )
    (survey_dir / "index.html").write_text(
        adapt_html_paths(html, "../assets/", "../static/"),
        encoding="utf-8",
    )

    shutil.copy2(root / "survey_app.js", static_dir / "survey_app.js")
    write_runtime_config(
        static_dir / "runtime-config.js",
        "",
        public_base_url.rstrip("/"),
        ".",
        "",
        True,
    )

    copy_tree(root / "assets", assets_dir)
    (output / ".nojekyll").write_text("", encoding="utf-8")
    shutil.copy2(output / "index.html", output / "404.html")


def main():
    parser = argparse.ArgumentParser(description="Build static survey bundle")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default="dist/cloudbase-static")
    parser.add_argument("--api-base-url", default="")
    parser.add_argument("--public-base-url", default="")
    parser.add_argument("--target", choices=["cloudbase", "github-pages"], default="cloudbase")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    output = Path(args.output).resolve()

    if output.exists():
        shutil.rmtree(output)

    if args.target == "github-pages":
        write_github_pages_bundle(root, output, args.public_base_url)
    else:
        write_cloudbase_bundle(root, output, args.api_base_url, args.public_base_url)

    print(f"Static bundle written to: {output}")
    print(f"Target: {args.target}")
    print(f"Survey entry: {output / 'index.html'}")


if __name__ == "__main__":
    main()
