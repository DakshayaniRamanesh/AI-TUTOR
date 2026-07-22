"""
Base graphics item functionality (Selection, Context Menu, Z-order, Lock, Focus)
"""

from PyQt6.QtWidgets import QMenu, QGraphicsItem
from PyQt6.QtCore import Qt

class BaseGraphicsItemMixin:
    """
    Mixin adding standard Freeform right-click menu options & interaction handles.
    """
    def setup_base_properties(self):
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemIsFocusable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.is_locked = False

    def build_context_menu(self, event_screen_pos) -> QMenu:
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #d1d1d6;
                border-radius: 8px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QMenu::item:selected {
                background-color: #007aff;
                color: white;
            }
        """)

        act_front = menu.addAction("Bring to Front")
        act_back = menu.addAction("Send to Back")
        menu.addSeparator()
        
        lock_txt = "Unlock" if getattr(self, "is_locked", False) else "Lock"
        act_lock = menu.addAction(lock_txt)
        
        menu.addSeparator()
        act_del = menu.addAction("Delete (Del)")

        action = menu.exec(event_screen_pos)
        if action == act_front:
            self.setZValue(self.zValue() + 1)
        elif action == act_back:
            self.setZValue(self.zValue() - 1)
        elif action == act_lock:
            self.is_locked = not getattr(self, "is_locked", False)
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not self.is_locked)
        elif action == act_del:
            scene = self.scene()
            if scene:
                scene.removeItem(self)

        return menu
