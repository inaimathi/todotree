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

__version__ = "0.0.0"

OPEN = {1, 9, 10}

def initialize():
    Logger.info(f" == v{__version__}")
    Logger.info(" === initializing model...")
    model.init()

NODE_HELD = False

def m_todo_title(todo):
    title = f"[ref=title]{todo['title']}[/ref]"
    checked = model.todo_checked_p(todo)
    if checked:
        title = f"[s]{title}[/s]"
    if todo['recurrence']:
        title = f"[color=#03fcfc]{title}[/color]"
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


def add_todo_body(node, todo):
    if todo['body']:
        body_node = TreeViewLabel(
            text=f"[ref=edit][i]{todo['body']}[/i][/ref]",
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

def add_subtree(root, parent, todo):
    if todo['deleted']:
        return None
    node = add_todo_node(root, parent, todo)
    if todo['id'] in OPEN:
        root.toggle_node(node)
    if todo['children']:
        for child in todo['children']:
            add_subtree(root, node, child)
    return node

class EditDialog:
    def __init__(self, root):
        self.root = root
        self.container = BoxLayout(orientation="vertical", size_hint=(1, 0.3), pos=(0,Window.height / 2))
        # with self.container.canvas.before:
        #     Color(.20, .06, .31, 1)
        #     Rectangle(
        #         size=(Window.width, Window.height),
        #         pos=self.container.pos
        #     )
        self.title_input = TextInput(text="")
        self.body_input = TextInput(text="", multiline=True)
        rec_box = BoxLayout(orientation="horizontal")
        self.one_time = CheckBox(group="todo_recurrence", active=True)
        self.daily = CheckBox(group="todo_recurrence")
        self.weekly = CheckBox(group="todo_recurrence")
        self.monthly = CheckBox(group="todo_recurrence")
        self.annually = CheckBox(group="todo_recurrence")
        rec_box.add_widget(Label(text='One Time', halign='left'))
        rec_box.add_widget(self.one_time)
        rec_box.add_widget(Label(text='Daily'))
        rec_box.add_widget(self.daily)
        rec_box.add_widget(Label(text='Weekly'))
        rec_box.add_widget(self.weekly)
        rec_box.add_widget(Label(text='Monthly'))
        rec_box.add_widget(self.monthly)
        rec_box.add_widget(Label(text='Annually'))
        rec_box.add_widget(self.annually)

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
        model.todo_update(self.current_todo['id'], delete=True)
        self.target_inst.root.remove_node(self.target_inst)
        self.root.remove_widget(self.container)

    def reset(self):
        self.title_input.text = ""
        self.body_input.text = ""
        self.delete.disabled = False
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
        elif self.annually.active:
            return 'annually'

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
            self.current_todo['title'] = self.title_input.text
            self.target_inst.text = m_todo_title(self.current_todo)
            self.current_todo['body'] = self.body_input.text
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
            elif recr == 'annually':
                self.annually.active = True
            else:
                self.one_time.active = True
        else:
            self.one_time.active = True



def Filters(parent):
    box = BoxLayout(orientation="horizontal", pos=(0,0), size_hint=(1, 0.1))
    labels = [Label(text="Unchecked"), Label(text="Checked"), Label(text="Deleted")]
    checks = [CheckBox(active=True), CheckBox(active=True), CheckBox()]

    for lbl, c in zip(labels, checks):
        box.add_widget(lbl)
        box.add_widget(c)

    parent.add_widget(box)
    return box

class TodoTree:
    def __init__(self, parent, pos=None, **rest):
        self.parent = parent
        self.pos = pos or (0,0)
        self.dialog = EditDialog(parent)
        self.render(model.todo_tree())

    def render(self, todos):
        self.scroll = ScrollView(do_scroll_x=False, do_scroll_y=True) # size=(Window.width, Window.height)
        self.tree = TreeView(
            hide_root=True, pos=self.pos, # size_hint=(0.9, 1),
            size_hint_y=None, height=self.scroll.height,
            on_node_expand=lambda inst, node: Logger.info(f"EXPANDING {getattr(node, 'todo_id', None)} -- {node}"),
            on_node_collapse=lambda inst, node: Logger.info(f"COLLAPSING {getattr(node, 'todo_id', None)} -- {node}")
        )
        self.tree.show_note_dialog = self.show_note_dialog
        for todo in todos:
            add_subtree(self.tree, None, todo)

        top_level_plus = TreeViewLabel(
            text="[font=Inconsolata][ref=addchild][+][/ref][/font]", markup=True,
            on_ref_press=lambda inst, ev: self.show_note_dialog(inst)
        )
        top_level_plus.root = self.tree
        self.tree.add_node(top_level_plus)
        self.scroll.add_widget(self.tree)
        self.parent.add_widget(self.scroll)

    def remove(self):
        self.parent.remove_widget(self.tree)

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
                ))
            else:
                self.dialog.edit(inst, None, lambda changes: (
                    todo := model.todo_add(changes['title'], body=changes.get('body'), recurrence=changes.get('recurrence'), parent_id=parent_id),
                    add_todo_node(inst.root, inst, todo),
                ))
            self.parent.add_widget(self.dialog.container)
        except kivy.uix.widget.WidgetException:
            Logger.info("  -- EXPLOSION")
            pass



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

        return root

if __name__ == '__main__':
    initialize()
    TodoTreeApp().run()
