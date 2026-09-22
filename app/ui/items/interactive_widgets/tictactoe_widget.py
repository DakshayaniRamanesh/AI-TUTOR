"""
Interactive Playable Tic-Tac-Toe Canvas Game Widget
Embedded 3x3 game supporting 2-player and single-player vs AI mode.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from ...theme_manager import ThemeManager
from ...kestrel_theme import MONO_FONT


class TicTacToeWidget(QWidget):
    """
    Playable Tic-Tac-Toe mini-game widget.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)

        self.board = [""] * 9
        self.current_turn = "X"
        self.vs_ai = True
        self.game_over = False
        self.score_x = 0
        self.score_o = 0

        self._init_ui()

    def _init_ui(self):
        c = ThemeManager.instance().get_colors()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(8)

        # Status & Turn
        status_row = QHBoxLayout()
        self.lbl_turn = QLabel("Turn: X", self)
        self.lbl_turn.setStyleSheet("font-weight: 700; color: #8b5cf6; font-size: 12px;")
        status_row.addWidget(self.lbl_turn)
        status_row.addStretch()

        self.btn_toggle_ai = QPushButton("vs AI", self)
        self.btn_toggle_ai.setFixedHeight(22)
        self.btn_toggle_ai.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_toggle_ai.setStyleSheet("""
            background: #8b5cf6; color: #fff; border-radius: 3px; font-size: 10px; font-weight: 700; padding: 0 6px;
        """)
        self.btn_toggle_ai.clicked.connect(self._toggle_ai_mode)
        status_row.addWidget(self.btn_toggle_ai)
        layout.addLayout(status_row)

        # 3x3 Grid
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)
        self.buttons = []

        for i in range(9):
            btn = QPushButton("", self)
            btn.setFixedSize(68, 64)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['panel_card_bg']};
                    border: 1px solid {c['border_color']};
                    border-radius: 8px;
                    font-size: 24px;
                    font-weight: 800;
                    font-family: {MONO_FONT};
                    color: {c['text_primary']};
                }}
                QPushButton:hover {{
                    background-color: rgba(139, 92, 246, 0.15);
                    border-color: #8b5cf6;
                }}
            """)
            btn.clicked.connect(lambda _, idx=i: self._make_move(idx))
            self.buttons.append(btn)
            self.grid_layout.addWidget(btn, i // 3, i % 3)

        layout.addLayout(self.grid_layout)

        # Bottom Bar: Score + Reset
        bottom_row = QHBoxLayout()
        self.lbl_score = QLabel("X: 0 | O: 0", self)
        self.lbl_score.setStyleSheet(f"font-size: 11px; font-weight: 600; color: {c['text_secondary']};")
        bottom_row.addWidget(self.lbl_score)
        bottom_row.addStretch()

        btn_restart = QPushButton("New Game", self)
        btn_restart.setFixedHeight(24)
        btn_restart.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_restart.setStyleSheet(f"""
            QPushButton {{
                background-color: {c['panel_card_bg']};
                border: 1px solid {c['border_color']};
                border-radius: 4px;
                color: {c['text_primary']};
                font-size: 10px;
                font-weight: 600;
                padding: 0 8px;
            }}
            QPushButton:hover {{ border-color: #8b5cf6; }}
        """)
        btn_restart.clicked.connect(self.reset_board)
        bottom_row.addWidget(btn_restart)

        layout.addLayout(bottom_row)

    def _toggle_ai_mode(self):
        self.vs_ai = not self.vs_ai
        self.btn_toggle_ai.setText("vs AI" if self.vs_ai else "2 Players")
        self.reset_board()

    def _make_move(self, idx: int):
        if self.game_over or self.board[idx] != "":
            return

        self.board[idx] = self.current_turn
        self._update_btn_ui(idx, self.current_turn)

        winner = self._check_winner()
        if winner:
            self._handle_winner(winner)
            return
        elif "" not in self.board:
            self.lbl_turn.setText("It's a Draw!")
            self.lbl_turn.setStyleSheet("font-weight: 700; color: #f59e0b; font-size: 12px;")
            self.game_over = True
            return

        # Next turn
        self.current_turn = "O" if self.current_turn == "X" else "X"
        self.lbl_turn.setText(f"Turn: {self.current_turn}")
        self.lbl_turn.setStyleSheet(f"font-weight: 700; color: {'#8b5cf6' if self.current_turn == 'X' else '#10b981'}; font-size: 12px;")

        # AI Turn
        if self.vs_ai and self.current_turn == "O" and not self.game_over:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(250, self._ai_move)

    def _ai_move(self):
        if self.game_over:
            return
        empty_indices = [i for i, val in enumerate(self.board) if val == ""]
        if not empty_indices:
            return

        # Simple smart AI: Win if possible, block opponent, or take center/random
        move = None
        # 1. Check if O can win
        for i in empty_indices:
            self.board[i] = "O"
            if self._check_winner() == "O":
                move = i
                self.board[i] = ""
                break
            self.board[i] = ""

        # 2. Check if X can win and block
        if move is None:
            for i in empty_indices:
                self.board[i] = "X"
                if self._check_winner() == "X":
                    move = i
                    self.board[i] = ""
                    break
                self.board[i] = ""

        # 3. Take center
        if move is None and 4 in empty_indices:
            move = 4

        # 4. Fallback random
        if move is None:
            import random
            move = random.choice(empty_indices)

        self._make_move(move)

    def _update_btn_ui(self, idx: int, player: str):
        btn = self.buttons[idx]
        btn.setText(player)
        color = "#8b5cf6" if player == "X" else "#10b981"
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({139 if player == 'X' else 16}, {92 if player == 'X' else 185}, {246 if player == 'X' else 129}, 0.15);
                border: 2px solid {color};
                border-radius: 8px;
                font-size: 24px;
                font-weight: 800;
                font-family: {MONO_FONT};
                color: {color};
            }}
        """)

    def _check_winner(self):
        lines = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8), # Rows
            (0, 3, 6), (1, 4, 7), (2, 5, 8), # Cols
            (0, 4, 8), (2, 4, 6)             # Diags
        ]
        for a, b, c in lines:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def _handle_winner(self, winner: str):
        self.game_over = True
        self.lbl_turn.setText(f"🎉 {winner} WINS!")
        color = "#8b5cf6" if winner == "X" else "#10b981"
        self.lbl_turn.setStyleSheet(f"font-weight: 800; color: {color}; font-size: 13px;")

        if winner == "X":
            self.score_x += 1
        else:
            self.score_o += 1
        self.lbl_score.setText(f"X: {self.score_x} | O: {self.score_o}")

    def reset_board(self):
        self.board = [""] * 9
        self.current_turn = "X"
        self.game_over = False
        self.lbl_turn.setText("Turn: X")
        self.lbl_turn.setStyleSheet("font-weight: 700; color: #8b5cf6; font-size: 12px;")
        c = ThemeManager.instance().get_colors()
        for btn in self.buttons:
            btn.setText("")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {c['panel_card_bg']};
                    border: 1px solid {c['border_color']};
                    border-radius: 8px;
                    font-size: 24px;
                    font-weight: 800;
                    font-family: {MONO_FONT};
                    color: {c['text_primary']};
                }}
                QPushButton:hover {{
                    background-color: rgba(139, 92, 246, 0.15);
                    border-color: #8b5cf6;
                }}
            """)
