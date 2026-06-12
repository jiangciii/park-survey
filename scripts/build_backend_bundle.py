import argparse
import json
import shutil
from pathlib import Path


ROOT_FILES_TO_COPY = [
    "survey_web.html",
    "survey_app.js",
    "runtime-config.js",
    "admin_login.html",
    "admin_dashboard.html",
    "admin_response.html",
    "admin_login.js",
    "admin_dashboard.js",
    "admin_response.js",
    "admin_app.css",
    ".dockerignore",
    ".env.example",
    "README.md",
]

BACKEND_FILES_TO_COPY = [
    "survey_server.py",
    "survey_backend.py",
    "requirements.txt",
    "Dockerfile",
]

DEFAULT_ENV_ID = "ce-d9gw2byci96a6f26e"
DEFAULT_SERVICE_NAME = "survey-backend"
DEFAULT_DB_MOUNT_DIR = "/mnt/sqlite"
DEFAULT_DB_FILE_NAME = "survey_data.db"
DEFAULT_CFS_ADDON_NAME = "surveySqliteStorage"
DEFAULT_CFS_INSTANCE_NAME = "survey-sqlite-storage"


def copy_file(src_root: Path, dst_root: Path, relative_path: str):
    src = src_root / relative_path
    dst = dst_root / relative_path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(src_root: Path, dst_root: Path, relative_path: str):
    src = src_root / relative_path
    dst = dst_root / relative_path
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def build_cloudbaserc(
    env_id: str,
    service_name: str,
    db_mount_dir: str,
    db_file_name: str,
    cfs_addon_name: str,
    cfs_instance_name: str,
):
    db_mount_dir = db_mount_dir.rstrip("/")
    db_path = f"{db_mount_dir}/{db_file_name}"
    return {
        "version": "2.0",
        "envId": env_id,
        "$schema": "https://framework-1258016615.tcloudbaseapp.com/schema/latest.json",
        "framework": {
            "name": service_name,
            "network": {
                "cloudBaseRun": True,
            },
            "addons": [
                {
                    "type": "CFS",
                    "name": cfs_addon_name,
                    "instanceName": cfs_instance_name,
                }
            ],
            "plugins": {
                "backend": {
                    "use": "@cloudbase/framework-plugin-container",
                    "inputs": {
                        "serviceName": service_name,
                        "servicePath": "/",
                        "localPath": "./",
                        "uploadType": "package",
                        "dockerfilePath": "./Dockerfile",
                        "buildDir": "./",
                        "isPublic": True,
                        "cpu": 0.5,
                        "mem": 1,
                        "minNum": 0,
                        "maxNum": 2,
                        "containerPort": 8000,
                        "envVariables": {
                            "SURVEY_HOST": "0.0.0.0",
                            "SURVEY_PORT": "8000",
                            "PORT": "8000",
                            "SURVEY_DB_PATH": db_path,
                            "SURVEY_PROJECT_ROOT": "/app",
                        },
                        "volumeMounts": {
                            db_mount_dir: cfs_addon_name,
                        },
                    },
                }
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Build backend deployment bundle for CloudBase Run")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output", default="dist/cloudbase-backend")
    parser.add_argument("--env-id", default=DEFAULT_ENV_ID)
    parser.add_argument("--service-name", default=DEFAULT_SERVICE_NAME)
    parser.add_argument("--db-mount-dir", default=DEFAULT_DB_MOUNT_DIR)
    parser.add_argument("--db-file-name", default=DEFAULT_DB_FILE_NAME)
    parser.add_argument("--cfs-addon-name", default=DEFAULT_CFS_ADDON_NAME)
    parser.add_argument("--cfs-instance-name", default=DEFAULT_CFS_INSTANCE_NAME)
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    backend_root = root / "后端"
    output = Path(args.output).resolve()

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    for file_name in ROOT_FILES_TO_COPY:
        copy_file(root, output, file_name)

    for file_name in BACKEND_FILES_TO_COPY:
        copy_file(backend_root, output, file_name)

    copy_tree(root, output, "assets")

    cloudbaserc = build_cloudbaserc(
        env_id=args.env_id,
        service_name=args.service_name,
        db_mount_dir=args.db_mount_dir,
        db_file_name=args.db_file_name,
        cfs_addon_name=args.cfs_addon_name,
        cfs_instance_name=args.cfs_instance_name,
    )
    (output / "cloudbaserc.json").write_text(
        json.dumps(cloudbaserc, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    db_path = f"{args.db_mount_dir.rstrip('/')}/{args.db_file_name}"
    print(f"Backend bundle written to: {output}")
    print(f"Persistent SQLite target: {db_path}")
    print("Bundle includes cloudbaserc.json with CloudBase container + CFS mount config.")


if __name__ == "__main__":
    main()
