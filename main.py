import kivy

kivy.require("2.2.1")

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.logger import Logger
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
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

def initialize():
    Logger.info(f" == v{__version__}")
    Logger.info(" === initializing model...")
    model.init()

NODE_HELD = False

def m_todo_title(todo):
    title = f"[ref=title]{todo['title']}[/ref]"
    if todo['checked']:
        title = f"[s]{title}[/s]"
    return f"[font=Inconsolata][ref=check][{'x' if todo['checked'] else ' '}][/ref] [ref=addchild][+][/ref][/font] {title}"

def m_todo_plus(todo):
    return "[ref=addchild][font=Inconsolata][+][/font][/ref]"


def _link(inst, ref, todo):
    if ref == 'check':
        if model.todo_update(todo['id'], check=(not todo['checked'])):
            todo['checked'] = not todo['checked']
            inst.text=m_todo_title(todo)
        else:
            Logger.info(f"   == Checking a TODO failed :(")
    elif ref == 'addchild':
        Logger.info(f" -- ADDING CHILD TO {todo}")
        inst.show_note_dialog(inst, None, parent_id=todo['id'])
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
    add_todo_body(node, todo)
    return node

def add_subtree(root, parent, todo):
    if todo['deleted']:
        return None
    node = add_todo_node(root, parent, todo)
    if todo['children']:
        for child in todo['children']:
            add_subtree(root, node, child)
    return node



class EditDialog:
    def __init__(self, root):
        self.root = root
        self.container = BoxLayout(orientation="vertical", size_hint=(1, 0.3), pos=(0,Window.height / 2))
        self.title_input = TextInput(text="")
        self.body_input = TextInput(text="", multiline=True)
        btn_box = BoxLayout(orientation="horizontal")
        self.cancel = Button(text="Cancel")
        self.cancel.bind(on_press=lambda inst: self.on_cancel())
        self.ok = Button(text="Save")
        self.ok.bind(on_press=lambda inst: self.on_ok())
        self.delete = Button(text="Delete")
        self.delete.bind(on_press=lambda inst: self.on_delete())
        self.container.add_widget(self.title_input)
        self.container.add_widget(self.body_input)
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


    def on_cancel(self):
        self.root.remove_widget(self.container)

    def on_ok(self):
        self.root.remove_widget(self.container)
        if self.on_save({
            "title": self.title_input.text,
            "body": self.body_input.text
        }):
            if self.current_todo is None:
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
            self.on_save = None
            self.current_todo = None
        self.root.remove_widget(self.container)

    def edit(self, inst, todo, on_save_cb):
        self.on_save = on_save_cb
        if todo is None:
            self.title_input.text = ""
            self.body_input.text = ""
            self.delete.disabled = True
            return
        self.delete.disabled = False
        self.current_todo = todo
        self.target_inst = inst
        self.title_input.text = todo['title']
        self.body_input.text = todo['body'] or ""


def Filters(parent):
    box = BoxLayout(orientation="horizontal", pos=(0,0), size_hint=(1, 0.1))
    labels = [Label(text="Unchecked"), Label(text="Checked"), Label(text="Deleted")]
    checks = [CheckBox(active=True), CheckBox(active=True), CheckBox()]

    for lbl, c in zip(labels, checks):
        box.add_widget(lbl)
        box.add_widget(c)

    return box


class TodoTreeApp(App):
    def on_start(self):
        Logger.info(" == STARTING APP")

    def on_stop(self):
        Logger.info(" == STOPPING APP")

    def build(self):
        root = FloatLayout()
        tree = TreeView(hide_root=True, pos=(0,0))
        # filters = Filters(root)
        # root.add_widget(filters)
        dialog = EditDialog(root)

        def __show_note_dialog(inst, todo=None, parent_id=None):
            try:
                if todo is not None:
                    dialog.edit(inst, todo, lambda changes: model.todo_update(todo['id'], **changes))
                elif parent_id is None:
                    dialog.edit(inst, None, lambda changes: (
                        todo := model.todo_add(changes['title'], changes['body'], parent_id=parent_id),
                        tmp := tree.children[0],
                        tree.remove_node(tmp),
                        add_todo_node(inst.root, None, todo),
                        tree.add_node(tmp)
                    ))
                else:
                    dialog.edit(inst, None, lambda changes: (
                        todo := model.todo_add(changes['title'], changes['body'], parent_id=parent_id),
                        add_todo_node(inst.root, inst, todo),
                    ))
                root.add_widget(dialog.container)
            except kivy.uix.widget.WidgetException:
                pass

        tree.show_note_dialog = __show_note_dialog
        root.add_widget(tree)

        for todo in model.todo_tree():
            add_subtree(tree, None, todo)

        top_level_add_plus = TreeViewLabel(
            text="[font=Inconsolata][ref=addchild][+][/ref][/font]", markup=True,
            on_ref_press=lambda inst, ev: __show_note_dialog(inst)
        )
        top_level_add_plus.root = tree
        tree.add_node(top_level_add_plus)

        return root

if __name__ == '__main__':
    initialize()
    TodoTreeApp().run()
