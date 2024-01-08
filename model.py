import itertools
import os
import sqlite3
from collections import defaultdict
from datetime import datetime

import plyer

import recurrence as recurr
import sql

DB_PATH = os.path.join(plyer.storagepath.get_documents_dir(), "todotree.db")
CONN = sqlite3.connect(DB_PATH)

def init():
    with CONN as cur:
        cur.execute(sql.createQ("todos", [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "parent_id INTEGER",
            "title TEXT", "body TEXT", "recurrence TEXT",
            "checked INTEGER", "deleted INTEGER",
            "created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "updated DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL"
        ]))
        cur.execute(sql.createQ("checks", [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "todo_id INTEGER", "checked INTEGER",
            "created DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL",
            "FOREIGN KEY(todo_id) REFERENCES todos(id)"
        ]))
        cur.execute(sql.createQ("ui_expand", [
            "todo_id INTEGER",
            "FOREIGN KEY(todo_id) REFERENCES todos(id) ON DELETE CASCADE"
        ]))
        cur.execute(sql.createQ("ui_filters", [
            "id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL",
            "name TEXT UNIQUE", "checked INTEGER"
        ]))
        try:
            cur.execute(*sql.insertQ("ui_filters", name="Unchecked", checked=True))
            cur.execute(*sql.insertQ("ui_filters", name="Checked", checked=True))
            cur.execute(*sql.insertQ("ui_filters", name="Deleted"))
        except sqlite3.IntegrityError:
            pass

def _drop():
    with CONN as cur:
        cur.execute("DROP TABLE todos")
        cur.execute("DROP TABLE checks")
        cur.execute("DROP TABLE ui_expand")
        cur.execute("DROP TABLE ui_filters")


def select(table_name, columns, where=None, join=None, order_by=None, transform=None):
    with CONN as cur:
        c = cur.cursor()
        if columns is None or columns == "*":
            columns = [el[1] for el in c.execute(f"PRAGMA table_info({table_name})").fetchall()]
        elif isinstance(columns, str):
            columns = [columns]
        query, args = sql.selectQ(table_name, columns, where=where, join=join, order_by=order_by)
        c.execute(query, args)
        res = (dict(zip(columns, vals)) for vals in c.fetchall())
        if transform is not None:
            return [transform(el) for el in res]
        return list(res)

def update(table_name, bindings, where):
    with CONN as cur:
        c = cur.cursor()
        q, args = sql.updateQ(table_name, **{**bindings, "where": where})
        c.execute(q, args)


def _transform_todo(raw):
    for btype in ['checked', 'deleted']:
        raw[btype] = bool(raw[btype])
    for dttype in ['created', 'updated']:
        if type(raw[dttype]) is str:
            raw[dttype] = datetime.fromisoformat(raw[dttype])
    if rec := raw['recurrence']:
        raw['recurrence'] = recurr.from_string(rec)
    return raw

def _recurred_checks():
    res = defaultdict(list)
    checks = select(
        "checks", ["checks.todo_id", "checks.created"],
        join=("todos", "todo_id", "todos.id"),
        where=("todos.recurrence", "IS NOT", None)
    )
    for el in checks:
        res[el['checks.todo_id']].append(datetime.fromisoformat(el['checks.created']))
    return dict(res)

def _checks_of(todo_id):
    return [datetime.fromisoformat(el['checks.created']) for el in select("checks", "checks.created", where={"todo_id": todo_id})]

def todos():
    checks = _recurred_checks()
    return [{**t, **{"checked_at": checks.get(t['id'])}} for t in select("todos", "*", transform=_transform_todo)]

def todo_tree():
    node_map = {}
    res = []
    all_todos = todos()
    for t in all_todos:
        t["children"] = []
        if t['parent_id'] is None:
            res.append(t)
        else:
            try:
                node_map[t['parent_id']]['children'].append(t)
            except KeyError:
                pass
        node_map[t['id']] = t
    return res

def todo_by(id):
    try:
        t = select("todos", "*", where={"id": id}, transform=_transform_todo)[0]
        if t['recurrence']:
            t['checked_at'] = _checks_of(t['id'])
        return t
    except IndexError:
        pass

def todo_shred(todo_id):
    todo = todo_by(id=todo_id)
    assert todo, "No such TODO"

    with CONN as cur:
        c = cur.cursor()
        c.execute(*sql.deleteQ("todos", where={"id": todo_id}))

def todo_add(title, body=None, recurrence=None, parent_id=None):
    with CONN as cur:
        c = cur.cursor()
        ins = {"title": title, "body": body}
        if recurrence == "once":
            recurrence = None
        if recurrence is not None:
            assert recurr.validate(recurrence), f"Invalid recurrence: {recurrence}"
            ins["recurrence"] = recurrence
        if parent_id is not None:
            assert todo_by(parent_id)
            ins["parent_id"] = parent_id
        c.execute(*sql.insertQ("todos", **ins))
        return todo_by(c.lastrowid)

def todo_streak(todo):
    if not todo['recurrence']:
        return None
    checked = set(dt.date() for dt in (todo['checked_at'] or []))
    checked_p = [
        (day.date() in checked)
        for day
        in recurr.days_range(todo['created'], datetime.now())
    ]
    streak = list(itertools.takewhile(lambda t: t, reversed(checked_p)))
    return len(streak)

def todo_checked_p(todo):
    if todo['recurrence'] and todo['checked_at']:
        should_recur = recurr.should_recur_p(todo['recurrence'], todo['checked_at'][-1])
        return todo['checked'] and todo['checked_at'] and not should_recur
    return todo['checked']

def todo_update(todo_id, check=None, title=None, body=None, recurrence=None, delete=None):
    todo = todo_by(id=todo_id)
    assert todo, "No such TODO"
    update = {}
    if delete is not None and not delete == todo['deleted']:
        update['deleted'] = delete
    if title is not None and not title == todo['title']:
        update['title'] = title
    if body is not None and not body == todo['body']:
        update['body'] = body
    if check is not None:
        update['checked'] = check
    if recurrence == "once" and todo['recurrence'] is not None:
        update['recurrence'] = None
    elif recurrence is not None:
        assert recurr.validate(recurrence), "Invalid recurrence"
        update['recurrence'] = recurrence
    if not update:
        return None
    with CONN as cur:
        c = cur.cursor()
        q, args = sql.updateQ("todos", **update, where={"id": todo_id})
        c.execute(q, args)
        if 'checked' in update:
            c.execute(*sql.insertQ('checks', todo_id=todo_id, checked=check))
    return todo_by(id=todo_id)


## UI state
def todo_collapse(todo_id):
    with CONN as cur:
        c = cur.cursor()
        c.execute(*sql.deleteQ("ui_expand", where={"todo_id": todo_id}))

def todo_expand(todo_id):
    with CONN as cur:
        c = cur.cursor()
        c.execute(*sql.insertQ("ui_expand", todo_id=todo_id))

def expanded_todos():
    return {el['todo_id'] for el in select("ui_expand", "todo_id")}

def ui_filter_update(filter_map):
    with CONN as cur:
        c = cur.cursor()
        for name, checked in filter_map.items():
            c.execute(*sql.updateQ("ui_filters", checked=checked, where={"name": name}))

def ui_filters():
    return {el['name']: bool(el['checked']) for el in  select("ui_filters", "*")}


def testing_todos():
    todo_add("Finish first cut of TodoTree", "This means having a 'good enough' app running no your phone that you can use to plan other stuff in your life. It doesn't mean 'never do any more work on it'.")
    todo_add("Finish first cut of Dumbfeed", "This means having a 'good enough' app running no your phone that you can use to read/listen to/keep running locally a bunch of your blogs. Including WordPress, substack, possibly Medium?, most generic XML feeds, and your literal blog. It doesn't mean 'never do any more work on it'.")
    todo_add("Have basic model runing", None, parent_id=1)
    todo_add("Be able to check things off", None, parent_id=1)
    todo_add("Check _this_ off", None, parent_id=4)
    tid = todo_add("Be able to add new TODOs", None, parent_id=1)
    todo_add("Add the rest of the TODOs for this project", None, parent_id=tid['id'])
    todo_add("Be able to edit existing TODOs", None, parent_id=1)
    todo_add("Stylin'", None, parent_id=1)
    todo_add("Be able to do cool things with dailies", None, parent_id=1)
    todo_add("Exercise", recurrence="daily")
    todo_add("Social", recurrence="daily at 11:00")
    todo_add("Job Search", recurrence="daily")
