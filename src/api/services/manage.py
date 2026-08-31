import datetime
import json
import pathlib
import sqlite3

libraries_path = pathlib.Path(__file__).parent.parent / 'static' / 'logs' / 'libraries_info.json'
sqlite_db_path = pathlib.Path(__file__).resolve().parents[2] / 'rag' / 'resources' / 'sqlite.db'

def get_all_libraries() -> dict:
    with open(libraries_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        return data


def save_libraries(libraries):
    with open(libraries_path, 'w', encoding='utf-8') as file:
        json.dump(libraries, file, ensure_ascii=False, indent=4)



def add_library_status(task_id: str, status_name: str = None, file_size: str = None,
                       file_name: str = None) -> None:
    all_libraries = get_all_libraries()
    task = all_libraries.get(task_id)
    if task:
        task['task_status'] = status_name
    else:
        task = {
            "task_id": task_id,
            "user_name": 'admin',
            'file_name': file_name,
            "file_size": file_size,
            "task_start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "task_end_time": "",
            "task_status": "extract"
        }
        all_libraries[task_id] = task
    with open(libraries_path, "w", encoding="utf-8") as file:
        json.dump(all_libraries, file, ensure_ascii=False, indent=4)



def get_libraries_list(page_no, page_size, sort_field, sort_type):
    libraries_list = get_all_libraries()
    libraries_list = list(libraries_list.values())
    start_index = (page_size * (page_no - 1))
    end_index = start_index + page_size

    libraries_list = libraries_list[start_index:end_index]
    if sort_field:
        if sort_type == 'desc':
            libraries_list = sorted(libraries_list, key=lambda x: x[sort_field], reverse=True)
        else:
            libraries_list = sorted(libraries_list, key=lambda x: x[sort_field], reverse=False)

    return {
        'libraries_list': libraries_list,
        'page_no': page_no,
        'page_size': page_size,
        'total_count': len(libraries_list),
    }


def update_libraries(md5, **kwargs):
    libraries_list = get_all_libraries()

    library_info = libraries_list.get(md5)
    if library_info:
        for key, value in kwargs.items():
            library_info[key] = value
        libraries_list[md5] = library_info
        save_libraries(libraries_list)


def delete_libraries(md5):
    libraries_list = get_all_libraries()
    libraries_list.pop(md5, None)
    save_libraries(libraries_list)


def get_files_by_ids(ids):
    if not ids:
        return []

    unique_ids = list(dict.fromkeys(ids))
    placeholders = ",".join(["?"] * len(unique_ids))
    query = f"SELECT * FROM File WHERE id IN ({placeholders})"

    with sqlite3.connect(sqlite_db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, unique_ids).fetchall()

    file_map = {}
    for row in rows:
        file_info = dict(row)
        file_info["file_path"] = "/static/file/" + file_info["file_path"]
        file_map[row["id"]] = file_info

    return [file_map[file_id] for file_id in unique_ids if file_id in file_map]
