import kivy

kivy.require("2.2.1")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.graphics.context_instructions import Color
from kivy.graphics.vertex_instructions import Rectangle
from kivy.logger import Logger
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.treeview import TreeView, TreeViewLabel, TreeViewNode

import model

LabelBase.register(
    "Inconsolata",
    fn_regular="./fonts/Inconsolata_Expanded-Bold.ttf",
    fn_italic="./fonts/Inconsolata_Expanded-Light.ttf",
    fn_bold="./fonts/Inconsolata_ExtraExpanded-ExtraBold.ttf",
    fn_bolditalic="./fonts/Inconsolata_ExtraExpanded-Light.ttf"
)

__version__ = "0.0.1"

OPEN = {}

def initialize():
    global OPEN
    Logger.info(f" == v{__version__}")
    Logger.info(" === initializing model...")
    model.init()
    OPEN = model.expanded_todos()

NODE_HELD = False
_REC_COLORS = {
    "daily": "#03fcfc",
    "weekly": "#f0de16",
    "monthly": "#f51df1"
}

def m_todo_title(todo):
    title = f"[ref=title]{todo['title'].strip() or '__________'}[/ref]"
    checked = model.todo_checked_p(todo)
    if checked:
        title = f"[s]{title}[/s]"
    if todo['recurrence']:
        rc = todo['recurrence']['recurs']
        title = f"[color={_REC_COLORS[rc]}]{title}[/color]"
    return f"[font=Inconsolata][ref=check][{'x' if checked else ' '}][/ref] [ref=addchild][+][/ref][/font] {title}"

def m_todo_plus(todo):
    return "[ref=addchild][font=Inconsolata][+][/font][/ref]"


def _link(inst, ref, todo):
    Logger.info(f"LINK -- {ref}")
    if ref == 'check':
        if updated := model.todo_update(todo['id'], check=(not model.todo_checked_p(todo))):
            for k, v in updated.items():
                todo[k] = v
            inst.text=m_todo_title(todo)
        else:
            Logger.info(f"   == Checking a TODO failed :(")
    elif ref == 'addchild':
        inst.show_note_dialog(inst, None, parent_id=todo['id'])
    elif ref == 'title':
        Logger.info(f"  YUP IT'S title")
        inst.show_note_dialog(inst, todo)
    else:
        inst.show_note_dialog(inst, todo)

def body_text(todo):
    res = []
    if todo['recurrence']:
        res.append(f"Total : {len(todo['checked_at'] or [])}")
        res.append(f"Streak: [font=Inconsolata]{''.join(['[x]'] * model.todo_streak(todo))}[ ][/font]")
    if todo['body']:
        res.append(f"[ref=edit][i]{todo['body']}[/i][/ref]")
    return '\n'.join(res)

def add_todo_body(node, todo):
    if todo['body'] or todo['recurrence']:
        body_node = TreeViewLabel(
            text=body_text(todo),
            markup=True,
            on_ref_press=lambda inst, ev: _link(inst, ev, todo))
        node.root.add_node(body_node, node)
        body_node.show_note_dialog = node.show_note_dialog
        node.body_node = body_node


def add_todo_node(root, parent, todo):
    node = root.add_node(TreeViewLabel(
        text=m_todo_title(todo),
        markup=True,
        on_ref_press=lambda inst, ev: _link(inst, ev, todo),
    ), parent)
    node.show_note_dialog = root.show_note_dialog
    node.root = root
    node.todo_id = todo['id']
    add_todo_body(node, todo)
    return node

def add_subtree(root, parent, todo, filter):
    if filter is not None and not filter(todo):
        return None
    node = add_todo_node(root, parent, todo)
    if todo['id'] in OPEN:
        root.toggle_node(node)
    if todo['children']:
        for child in todo['children']:
            add_subtree(root, node, child, filter)
    return node

def _vbox(*elems):
    box = BoxLayout(orientation="vertical")
    for el in elems:
        box.add_widget(el)
    return box

class EditDialog:
    def __init__(self, root):
        self.root = root
        self.container = BoxLayout(orientation="vertical", size_hint=(1, 0.3), pos=(0,Window.height / 2))
        with self.container.canvas.before:
            Color(0, 0, 0, 0.9)
            x, y = self.container.pos
            Rectangle(
                size=(Window.width * 2, self.container.height * 2),
                pos=(x-10, y-10)
            )
        self.title_input = TextInput(text="")
        self.body_input = TextInput(text="", multiline=True)
        rec_box = BoxLayout(orientation="horizontal")
        self.one_time = CheckBox(group="todo_recurrence", active=True)
        self.daily = CheckBox(group="todo_recurrence")
        self.weekly = CheckBox(group="todo_recurrence")
        self.monthly = CheckBox(group="todo_recurrence")
        rec_box.add_widget(_vbox(self.one_time, Label(text="One Time")))
        rec_box.add_widget(_vbox(self.daily, Label(text="Daily")))
        rec_box.add_widget(_vbox(self.weekly, Label(text="Weekly")))
        rec_box.add_widget(_vbox(self.monthly, Label(text="Monthly")))

        btn_box = BoxLayout(orientation="horizontal")
        self.cancel = Button(text="Cancel")
        self.cancel.bind(on_press=lambda inst: self.on_cancel())
        self.ok = Button(text="Save")
        self.ok.bind(on_press=lambda inst: self.on_ok())
        self.delete = Button(text="Delete")
        self.delete.bind(on_press=lambda inst: self.on_delete())
        self.container.add_widget(self.title_input)
        self.container.add_widget(self.body_input)
        self.container.add_widget(rec_box)
        self.container.add_widget(btn_box)
        self.current_todo = None
        self.target_inst = None
        btn_box.add_widget(self.cancel)
        btn_box.add_widget(self.delete)
        btn_box.add_widget(self.ok)

    def on_delete(self):
        deleted = not self.current_todo['deleted']
        model.todo_update(self.current_todo['id'], delete=deleted)
        if not (model.ui_filters()['Deleted'] == deleted):
            self.target_inst.root.remove_node(self.target_inst)
        self.reset()
        self.root.remove_widget(self.container)

    def reset(self):
        self.title_input.text = ""
        self.body_input.text = ""
        self.delete.disabled = False
        self.delete.text = "Delete"
        self.on_save = None
        self.current_todo = None

    def on_cancel(self):
        self.reset()
        self.root.remove_widget(self.container)

    def get_recurrence(self):
        if self.daily.active:
            return 'daily'
        elif self.weekly.active:
            return 'weekly'
        elif self.monthly.active:
            return 'monthly'
        return 'once'

    def on_ok(self):
        Logger.info(f"OK CLICKED")
        self.root.remove_widget(self.container)
        Logger.info(f"  RECURRENCE: {self.get_recurrence()}")
        change = {
            "title": self.title_input.text,
            "body": self.body_input.text,
            "recurrence": self.get_recurrence()
        }
        Logger.info(f"  CHANGE: {change}")
        save_res = self.on_save(change)
        Logger.info(f"  SAVE RES: {save_res}")
        if save_res:
            if self.current_todo is None:
                self.reset()
                self.root.remove_widget(self.container)
                return
            for k, v in save_res.items():
                self.current_todo[k] = v
            for k in list(self.current_todo.keys()):
                if k not in save_res:
                    del self.current_todo[k]
            self.target_inst.text = m_todo_title(save_res)
            if hasattr(self.target_inst, 'body_node') and self.target_inst.body_node is not None:
                Logger.info("HAS BODY_NODE")
                if not self.current_todo['body']:
                    Logger.info("  FRESHLY EMPTY, REMOVING EXISTING BODY NODE")
                    self.target_inst.root.remove_node(self.target_inst.body_node)
                    self.target_inst.body_node = None
                else:
                    Logger.info("  NEW TEXT")
                    self.target_inst.body_node.text = self.current_todo['body']
            else:
                if self.current_todo['body']:
                    Logger.info("  FRESHLY FILLED BODY, ADDING NODE")
                    add_todo_body(self.target_inst, self.current_todo)
            self.reset()
        self.root.remove_widget(self.container)

    def edit(self, inst, todo, on_save_cb):
        self.on_save = on_save_cb
        if todo is None:
            self.title_input.text = ""
            self.body_input.text = ""
            self.delete.disabled = True
            self.one_time.active = True
            return
        self.delete.disabled = False
        if todo['deleted']:
            self.delete.text = "Undelete"
        self.current_todo = todo
        self.target_inst = inst
        self.title_input.text = todo['title']
        self.body_input.text = todo['body'] or ""
        if todo['recurrence']:
            recr = todo['recurrence']['recurs']
            if recr == 'daily':
                self.daily.active = True
            elif recr == 'weekly':
                self.weekly.active = True
            elif recr == 'monthly':
                self.monthly.active = True
            else:
                self.one_time.active = True
        else:
            self.one_time.active = True

def _filter_from_state():
    filters = model.ui_filters()
    def _filter_todo(todo):
        if filters['Deleted'] and todo['deleted']:
            return True
        elif not todo['deleted']:
            return (
                (filters['Unchecked'] and not model.todo_checked_p(todo))
                or (filters['Checked'] and model.todo_checked_p(todo))
            )
    return _filter_todo

class TodoTree:
    def __init__(self, parent, pos=None, **rest):
        self.parent = parent
        self.pos = pos or (0,0)
        self.dialog = EditDialog(parent)
        self.render(model.todo_tree(), _filter_from_state())

    def re_render(self, todos, filter=None):
        global OPEN
        OPEN = model.expanded_todos()
        self.remove()
        self.render(todos, filter)

    def _maybe_node_id(self, node, fn):
        if (tid := getattr(node, 'todo_id', None)) is not None:
            return fn(tid)

    def render(self, todos, filter=None):
        self.scroll = ScrollView(do_scroll_x=False, do_scroll_y=True) # size=(Window.width, Window.height)
        self.tree = TreeView(
            hide_root=True, pos=self.pos, # size_hint=(0.9, 1),
            size_hint_y=None, height=self.scroll.height / 2,
            on_node_expand=lambda inst, node: self._maybe_node_id(node, model.todo_expand),
            on_node_collapse=lambda inst, node: self._maybe_node_id(node, model.todo_collapse)
        )
        self.tree.show_note_dialog = self.show_note_dialog
        for todo in todos:
            if filter is None or filter(todo):
                add_subtree(self.tree, None, todo, filter)

        top_level_plus = TreeViewLabel(
            text="[font=Inconsolata][ref=addchild][+][/ref][/font]", markup=True,
            on_ref_press=lambda inst, ev: self.show_note_dialog(inst)
        )
        top_level_plus.root = self.tree
        self.tree.add_node(top_level_plus)
        self.scroll.add_widget(self.tree)
        self.parent.add_widget(self.scroll)

    def remove(self):
        self.parent.remove_widget(self.scroll)

    def show_note_dialog(self, inst, todo=None, parent_id=None):
        Logger.info(f"  -- CALLED self.show_note_dialog {inst} {todo} {parent_id}")
        try:
            if todo is not None:
                self.dialog.edit(inst, todo, lambda changes: model.todo_update(todo['id'], **changes))
            elif parent_id is None:
                self.dialog.edit(inst, None, lambda changes: (
                    todo := model.todo_add(changes['title'], body=changes.get('body'), recurrence=changes.get('recurrence'), parent_id=parent_id),
                    tmp := self.tree.children[0],
                    self.tree.remove_node(tmp),
                    add_todo_node(inst.root, None, todo),
                    self.tree.add_node(tmp)
                )[0])
            else:
                self.dialog.edit(inst, None, lambda changes: (
                    todo := model.todo_add(changes['title'], body=changes.get('body'), recurrence=changes.get('recurrence'), parent_id=parent_id),
                    add_todo_node(inst.root, inst, todo),
                )[0])
            self.parent.add_widget(self.dialog.container)
        except kivy.uix.widget.WidgetException:
            Logger.info("  -- EXPLOSION")
            pass

def Filters(parent, tree):
    box = BoxLayout(orientation="horizontal", pos=(0,0), size_hint=(1, 0.1))

    checks = []
    initial_state = model.ui_filters()

    def _update_tree():
        unchecked, checked, deleted = [c.active for c in checks]
        model.ui_filter_update({"Unchecked": unchecked, "Checked": checked, "Deleted": deleted})
        tree.re_render(model.todo_tree(), _filter_from_state())
        parent.remove_widget(box)
        parent.add_widget(box)

    for name, active in initial_state.items():
        chk = CheckBox(active=active)
        checks.append(chk)
        chk.bind(active=lambda inst, val: _update_tree())
        box.add_widget(Label(text=name))
        box.add_widget(chk)

    parent.add_widget(box)
    return box

## TODO - factor out TreeView into separate class
##         - give it external methods to re-render on filtering changes
##         - contain it as much as possible so that we can get scrolling down trivially by
##           wrapping it in a ScrollView later

class TodoTreeApp(App):
    def on_start(self):
        Logger.info(" == STARTING APP")

    def on_stop(self):
        Logger.info(" == STOPPING APP")

    def build(self):
        root = FloatLayout()
        tree = TodoTree(root)
        filters = Filters(root, tree)

        return root

if __name__ == '__main__':
    initialize()
    TodoTreeApp().run()
