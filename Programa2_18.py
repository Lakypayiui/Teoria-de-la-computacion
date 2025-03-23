import random
import pygame
import itertools
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Límite de memoria en bytes (8GB)
MEMORY_LIMIT = 8 * 1024 * 1024 * 1024

# Inicializar Pygame
pygame.init()

class NFAGame:
    def __init__(self):
        self.states = set(f'q{i}' for i in range(16))
        self.alphabet = {'r', 'b'}  # 'r' para rojo, 'b' para blanco
        self.start_state_player1 = 'q0'
        self.start_state_player2 = 'q2'
        self.win_state_player1 = 'q15'
        self.win_state_player2 = 'q13'
        
        self.transitions = {
            ('q0', 'r'): {'q1', 'q4', 'q5'}, ('q0', 'b'): {'q1', 'q4', 'q5'},
            ('q1', 'r'): {'q0', 'q2', 'q4', 'q5', 'q6'}, ('q1', 'b'): {'q0', 'q2', 'q4', 'q5', 'q6'},
            ('q2', 'r'): {'q1', 'q3', 'q5', 'q6', 'q7'}, ('q2', 'b'): {'q1', 'q3', 'q5', 'q6', 'q7'},
            ('q3', 'r'): {'q2', 'q6', 'q7'}, ('q3', 'b'): {'q2', 'q6', 'q7'},
            ('q4', 'r'): {'q0', 'q1', 'q5', 'q8', 'q9'}, ('q4', 'b'): {'q0', 'q1', 'q5', 'q8', 'q9'},
            ('q5', 'r'): {'q0', 'q1', 'q2', 'q4', 'q6', 'q8', 'q9', 'q10'}, ('q5', 'b'): {'q0', 'q1', 'q2', 'q4', 'q6', 'q8', 'q9', 'q10'},
            ('q6', 'r'): {'q1', 'q2', 'q3', 'q5', 'q7', 'q9', 'q10', 'q11'}, ('q6', 'b'): {'q1', 'q2', 'q3', 'q5', 'q7', 'q9', 'q10', 'q11'},
            ('q7', 'r'): {'q2', 'q3', 'q6', 'q10', 'q11'}, ('q7', 'b'): {'q2', 'q3', 'q6', 'q10', 'q11'},
            ('q8', 'r'): {'q4', 'q5', 'q9', 'q12', 'q13'}, ('q8', 'b'): {'q4', 'q5', 'q9', 'q12', 'q13'},
            ('q9', 'r'): {'q4', 'q5', 'q6', 'q8', 'q10', 'q12', 'q13', 'q14'}, ('q9', 'b'): {'q4', 'q5', 'q6', 'q8', 'q10', 'q12', 'q13', 'q14'},
            ('q10', 'r'): {'q5', 'q6', 'q7', 'q9', 'q11', 'q13', 'q14', 'q15'}, ('q10', 'b'): {'q5', 'q6', 'q7', 'q9', 'q11', 'q13', 'q14', 'q15'},
            ('q11', 'r'): {'q6', 'q7', 'q10', 'q14', 'q15'}, ('q11', 'b'): {'q6', 'q7', 'q10', 'q14', 'q15'},
            ('q12', 'r'): {'q8', 'q9', 'q13'}, ('q12', 'b'): {'q8', 'q9', 'q13'},
            ('q13', 'r'): {'q8', 'q9', 'q10', 'q12', 'q14'}, ('q13', 'b'): {'q8', 'q9', 'q10', 'q12', 'q14'},
            ('q14', 'r'): {'q9', 'q10', 'q11', 'q13', 'q15'}, ('q14', 'b'): {'q9', 'q10', 'q11', 'q13', 'q15'},
            ('q15', 'r'): {'q10', 'q11', 'q14'}, ('q15', 'b'): {'q10', 'q11', 'q14'}
        }
        
        self.player1_turn = random.choice([True, False])
        self.board_positions = {f'q{i}': (50 + (i % 4) * 100, 50 + (i // 4) * 100) for i in range(16)}
        self.color_map = {}
        for i in range(16):
            row, col = i // 4, i % 4
            self.color_map[f'q{i}'] = (255, 255, 255) if (row + col) % 2 == 0 else (255, 0, 0)

        pygame.display.set_caption("NFA Game")
        self.screen = pygame.display.set_mode((1200, 600))
        self.clock = pygame.time.Clock()
        
        self.game_state = "menu"
        self.n = None
        self.mode = None
        self.input_n = ""
        self.input_player1 = ""
        self.input_player2 = ""
        self.active_field = None
        self.game_over = False
        self.winner = None
        self.error_message = None
        self.scroll_offset = 0
        self.scrollbar_dragging = False
        self.scroll_drag_start_y = 0
        self.player1_paused = False
        self.player2_paused = False
        
        # Variables para el árbol móvil
        self.tree_offset_x = 400  # Posición inicial fija del árbol en x
        self.tree_offset_y = 0    # Posición inicial del árbol en y
        self.tree_dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0

        self.executor = ThreadPoolExecutor(max_workers=2)

    def initialize_game(self, n):
        if self.mode == "auto" and not (3 <= n <= 7):
            raise ValueError("El número de movimientos en modo automático debe estar entre 3 y 7")
        if self.mode == "manual" and not (3 <= n <=100):
            raise ValueError("El número de movimientos en modo manual debe estar entre 3 y 100")
        self.n = n
        self.board_surface = pygame.Surface((400, 400))
        self.tree_surface = pygame.Surface((800, max(600, (n + 1) * 150)))
        self.scroll_offset = 0
        self.board_buffer = self.pre_render_board()

    def generate_all_combinations_batch(self, start_state, n, input_string, filename):
        """Genera todas las combinaciones de estados válidas respetando la cadena de entrada."""
        batch = []
        batch_size_bytes = 0
        
        queue = deque([(start_state, [start_state], 0)])
        seen_paths = set()
        
        with open(filename, 'w', encoding='utf-8') as f:
            while queue:
                current_state, current_path, step = queue.popleft()
                
                if step == n:
                    path_str = " -> ".join(current_path)
                    if path_str not in seen_paths:
                        seen_paths.add(path_str)
                        line = path_str + "\n"
                        line_size = sys.getsizeof(line)
                        
                        if batch_size_bytes + line_size > MEMORY_LIMIT:
                            f.writelines(batch)
                            batch = []
                            batch_size_bytes = 0
                        
                        batch.append(line)
                        batch_size_bytes += line_size
                    continue
                
                required_color = input_string[step]
                expected_color = (255, 0, 0) if required_color == 'r' else (255, 255, 255)
                
                for symbol in self.alphabet:
                    transition_key = (current_state, symbol)
                    if transition_key in self.transitions:
                        for next_state in self.transitions[transition_key]:
                            if self.color_map[next_state] == expected_color:
                                new_path = current_path + [next_state]
                                queue.append((next_state, new_path, step + 1))
            
            if batch:
                f.writelines(batch)

    def pre_render_board(self):
        buffer = pygame.Surface((400, 400))
        for row in range(4):
            for col in range(4):
                color = (255, 255, 255) if (row + col) % 2 == 0 else (255, 0, 0)
                pygame.draw.rect(buffer, color, (col * 100, row * 100, 100, 100))

        for i in range(4):
            pygame.draw.line(buffer, (0, 0, 0), (0, i * 100), (400, i * 100), 1)
            pygame.draw.line(buffer, (0, 0, 0), (i * 100, 0), (i * 100, 400), 1)

        font = pygame.font.SysFont(None, 24)
        for state, pos in self.board_positions.items():
            text = font.render(state, True, (0, 0, 0))
            buffer.blit(text, (pos[0] - 10, pos[1] - 10))
            pygame.draw.circle(buffer, (200, 200, 200), pos, 15, 1)

        pygame.draw.circle(buffer, (0, 200, 0), self.board_positions[self.start_state_player1], 17, 2)
        pygame.draw.circle(buffer, (200, 0, 0), self.board_positions[self.start_state_player2], 17, 2)
        pygame.draw.circle(buffer, (0, 0, 200), self.board_positions[self.win_state_player1], 17, 2)
        pygame.draw.circle(buffer, (200, 200, 0), self.board_positions[self.win_state_player2], 17, 2)
        return buffer

    def generate_winning_paths(self, start_state, transitions, n, input_string, filename, win_state):
        batch = []
        batch_size_bytes = 0
        seen_paths = set()
        
        queue = deque([(start_state, [start_state], 0)])
        
        with open(filename, 'w', encoding='utf-8') as f:
            while queue:
                current_state, current_path, step = queue.popleft()
                
                if step == n and current_state == win_state:
                    path_str = " -> ".join(current_path)
                    if path_str not in seen_paths:
                        seen_paths.add(path_str)
                        line = path_str + "\n"
                        line_size = sys.getsizeof(line)
                        
                        if batch_size_bytes + line_size > MEMORY_LIMIT:
                            f.writelines(batch)
                            batch = []
                            batch_size_bytes = 0
                        
                        batch.append(line)
                        batch_size_bytes += line_size
                    continue
                
                if step >= n:
                    continue
                    
                required_color = input_string[step]
                expected_color = (255, 0, 0) if required_color == 'r' else (255, 255, 255)
                for symbol in self.alphabet:
                    transition_key = (current_state, symbol)
                    if transition_key in transitions:
                        for next_state in transitions[transition_key]:
                            if self.color_map[next_state] == expected_color:
                                new_path = current_path + [next_state]
                                queue.append((next_state, new_path, step + 1))
        
        if batch:
            with open(filename, 'a', encoding='utf-8') as f:
                f.writelines(batch)

    def load_paths_from_file(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                return [line.strip().split(" -> ") for line in f.readlines()]
        except FileNotFoundError:
            return []

    def select_valid_path(self, current_state, occupied_state, winning_paths, current_step, input_string):
        valid_paths = [
            path for path in winning_paths
            if path[current_step] == current_state and path[current_step + 1] != occupied_state
        ]
        return random.choice(valid_paths) if valid_paths else None

    def generate_random_input(self, n):
        prefix = ''.join(random.choice(['r', 'b']) for _ in range(n - 1))
        return prefix + 'b'

    def draw_player_path(self, surface, current_state, color):
        pygame.draw.circle(surface, color, self.board_positions[current_state], 10)

    def draw_path_tree(self, all_paths_player1, all_paths_player2, player1_history, player2_history):
        self.tree_surface.fill((255, 255, 255))
        font = pygame.font.SysFont(None, 20)
        level_height = 150
        tree_width = 400
        
        def draw_branch(paths, start_x, color, history_states):
            all_states = [f'q{i}' for i in range(16)]
            x_spacing = tree_width / 16
            x_positions = {state: start_x + i * x_spacing for i, state in enumerate(all_states)}

            for level in range(self.n):
                y = 50 + level * level_height
                next_y = 50 + (level + 1) * level_height
                for state in all_states:
                    x = x_positions[state]
                    for symbol in self.alphabet:
                        transition_key = (state, symbol)
                        if transition_key in self.transitions:
                            for next_state in self.transitions[transition_key]:
                                next_x = x_positions[next_state]
                                pygame.draw.line(self.tree_surface, (150, 150, 150), (int(x), int(y)), (int(next_x), int(next_y)), 1)

            for level in range(self.n + 1):
                y = 50 + level * level_height
                for state in all_states:
                    x = x_positions[state]
                    node_color = (200, 200, 200)
                    if level < len(history_states) and state == history_states[level]:
                        node_color = color
                    pygame.draw.circle(self.tree_surface, node_color, (int(x), int(y)), 8)
                    text = font.render(state, True, (0, 0, 0))
                    self.tree_surface.blit(text, (int(x) - 10, int(y) - 20))

                    if level > 0 and level < len(history_states):
                        current_state = history_states[level]
                        prev_state = history_states[level - 1]
                        if current_state in all_states and prev_state in all_states:
                            parent_x = x_positions[prev_state]
                            parent_y = y - level_height
                            if state == current_state:
                                pygame.draw.line(self.tree_surface, color, (int(x), int(y)), (int(parent_x), int(parent_y)), 2)

        draw_branch(all_paths_player1, 0, (0, 0, 255), player1_history)
        draw_branch(all_paths_player2, 400, (0, 255, 0), player2_history)
        
        title_font = pygame.font.SysFont(None, 28)
        self.tree_surface.blit(title_font.render("Árbol Jugador 1", True, (0, 0, 255)), (100, 10))
        self.tree_surface.blit(title_font.render("Árbol Jugador 2", True, (0, 255, 0)), (500, 10))

    def draw_scrollbar(self):
        tree_height = self.tree_surface.get_height()
        view_height = 600
        if tree_height <= view_height:
            return None

        scrollbar_width = 20
        scrollbar_height = view_height
        scrollbar_x = self.tree_offset_x + 780  # Ajustado al desplazamiento del árbol
        scrollbar_y = self.tree_offset_y

        pygame.draw.rect(self.screen, (200, 200, 200), (scrollbar_x, scrollbar_y, scrollbar_width, scrollbar_height))

        thumb_height = max(20, (view_height / tree_height) * view_height)
        max_scroll = tree_height - view_height
        thumb_y = (self.scroll_offset / max_scroll) * (view_height - thumb_height) if max_scroll > 0 else 0
        thumb_rect = pygame.Rect(scrollbar_x, scrollbar_y + thumb_y, scrollbar_width, thumb_height)

        pygame.draw.rect(self.screen, (100, 100, 100), thumb_rect)
        return thumb_rect

    def draw_menu(self):
        self.screen.fill((200, 200, 200))
        font = pygame.font.SysFont(None, 36)
        
        auto_button = pygame.Rect(400, 200, 400, 100)
        pygame.draw.rect(self.screen, (0, 200, 0), auto_button)
        auto_text = font.render("Iniciar Modo Automático", True, (255, 255, 255))
        self.screen.blit(auto_text, (auto_button.x + 50, auto_button.y + 30))
        
        manual_button = pygame.Rect(400, 350, 400, 100)
        pygame.draw.rect(self.screen, (0, 0, 200), manual_button)
        manual_text = font.render("Iniciar Modo Manual", True, (255, 255, 255))
        self.screen.blit(manual_text, (manual_button.x + 70, manual_button.y + 30))
        
        return auto_button, manual_button

    def draw_manual_input(self):
        self.screen.fill((200, 200, 200))
        font = pygame.font.SysFont(None, 36)
        
        n_label = font.render("Número de movimientos (3-100):", True, (0, 0, 0))
        n_rect = pygame.Rect(400, 150, 400, 50)
        pygame.draw.rect(self.screen, (255, 255, 255), n_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), n_rect, 2 if self.active_field == "n" else 1)
        n_text = font.render(self.input_n, True, (0, 0, 0))
        self.screen.blit(n_label, (400, 100))
        self.screen.blit(n_text, (n_rect.x + 10, n_rect.y + 10))
        
        p1_label = font.render(f"Cadena Jugador 1 ({self.n if self.n else 'n'} 'r' o 'b'):", True, (0, 0, 0))
        p1_rect = pygame.Rect(400, 300, 400, 50)
        pygame.draw.rect(self.screen, (255, 255, 255), p1_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), p1_rect, 2 if self.active_field == "p1" else 1)
        p1_text = font.render(self.input_player1, True, (0, 0, 0))
        self.screen.blit(p1_label, (400, 250))
        self.screen.blit(p1_text, (p1_rect.x + 10, p1_rect.y + 10))
        
        p2_label = font.render(f"Cadena Jugador 2 ({self.n if self.n else 'n'} 'r' o 'b'):", True, (0, 0, 0))
        p2_rect = pygame.Rect(400, 450, 400, 50)
        pygame.draw.rect(self.screen, (255, 255, 255), p2_rect)
        pygame.draw.rect(self.screen, (0, 0, 0), p2_rect, 2 if self.active_field == "p2" else 1)
        p2_text = font.render(self.input_player2, True, (0, 0, 0))
        self.screen.blit(p2_label, (400, 400))
        self.screen.blit(p2_text, (p2_rect.x + 10, p2_rect.y + 10))
        
        start_button = pygame.Rect(500, 550, 200, 50)
        pygame.draw.rect(self.screen, (0, 200, 0), start_button)
        start_text = font.render("Iniciar", True, (255, 255, 255))
        self.screen.blit(start_text, (start_button.x + 50, start_button.y + 10))
        
        return n_rect, p1_rect, p2_rect, start_button

    def draw_play_again(self):
        font = pygame.font.SysFont(None, 36)
        play_again_button = pygame.Rect(500, 500, 200, 50)
        pygame.draw.rect(self.screen, (0, 200, 0), play_again_button)
        play_again_text = font.render("Jugar de Nuevo", True, (255, 255, 255))
        self.screen.blit(play_again_text, (play_again_button.x + 20, play_again_button.y + 10))
        return play_again_button

    def draw_error_message(self):
        self.screen.fill((200, 200, 200))
        font = pygame.font.SysFont(None, 36)
        error_text = font.render(self.error_message, True, (255, 0, 0))
        self.screen.blit(error_text, (300, 300))
        play_again_button = self.draw_play_again()
        return play_again_button

    def render_game_state(self, current_state_player1, current_state_player2, moves_player1, moves_player2, player1_history, player2_history, all_paths_player1, all_paths_player2, turn):
        self.board_surface.blit(self.board_buffer, (0, 0))
        self.draw_player_path(self.board_surface, current_state_player1, (0, 0, 255))
        self.draw_player_path(self.board_surface, current_state_player2, (0, 255, 0))

        self.draw_path_tree(all_paths_player1, all_paths_player2, player1_history, player2_history)
        self.screen.fill((200, 200, 200))
        
        # Tablero fijo en su posición original
        self.screen.blit(self.board_surface, (0, 100))
        # Árbol con desplazamiento y scroll
        self.screen.blit(self.tree_surface, (self.tree_offset_x, self.tree_offset_y), (0, self.scroll_offset, 800, 600))

        font = pygame.font.SysFont(None, 24)
        self.screen.blit(font.render(f"Turno: {'Jugador 1' if turn else 'Jugador 2'}", True, (0, 0, 0)), (10, 10))
        self.screen.blit(font.render(f"P1: {current_state_player1} ({moves_player1}/{self.n})", True, (0, 0, 255)), (10, 40))
        self.screen.blit(font.render(f"P2: {current_state_player2} ({moves_player2}/{self.n})", True, (0, 255, 0)), (10, 70))

        if self.game_over:
            result_font = pygame.font.SysFont(None, 36)
            self.screen.blit(result_font.render(f"¡{self.winner} gana!", True, (0, 0, 0)), (400, 550))

        thumb_rect = self.draw_scrollbar()
        # Dibujar el botón "Jugar de Nuevo" después del árbol y la barra de desplazamiento
        if self.game_over:
            play_again_button = self.draw_play_again()
        else:
            play_again_button = None

        pygame.display.flip()
        return thumb_rect, play_again_button

    def process_game_with_visualization(self):
        running = True
        auto_button, manual_button = None, None
        n_rect, p1_rect, p2_rect, start_button = None, None, None, None
        play_again_button = None
        thumb_rect = None
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    mouse_pos = pygame.mouse.get_pos()
                    if self.game_state == "menu":
                        if auto_button and auto_button.collidepoint(mouse_pos):
                            self.mode = "auto"
                            self.n = random.randint(3, 7)
                            self.initialize_game(self.n)
                            self.game_state = "playing"
                        elif manual_button and manual_button.collidepoint(mouse_pos):
                            self.mode = "manual"
                            self.game_state = "input"
                    elif self.game_state == "input":
                        if n_rect and n_rect.collidepoint(mouse_pos):
                            self.active_field = "n"
                        elif p1_rect and p1_rect.collidepoint(mouse_pos):
                            self.active_field = "p1"
                        elif p2_rect and p2_rect.collidepoint(mouse_pos):
                            self.active_field = "p2"
                        elif start_button and start_button.collidepoint(mouse_pos):
                            try:
                                n = int(self.input_n)
                                if 3 <= n <= 20 and len(self.input_player1) == n and len(self.input_player2) == n and \
                                   all(c in self.alphabet for c in self.input_player1) and all(c in self.alphabet for c in self.input_player2):
                                    self.initialize_game(n)
                                    self.game_state = "playing"
                                else:
                                    print("Entradas inválidas. Verifique n (3-20) y cadenas.")
                            except ValueError:
                                print("Número de movimientos inválido.")
                    elif self.game_state in ["playing", "game_over"]:
                        if play_again_button and play_again_button.collidepoint(mouse_pos) and self.game_over:
                            self.__init__()
                            self.game_state = "menu"
                        elif self.game_state == "error" and play_again_button and play_again_button.collidepoint(mouse_pos):
                            self.__init__()
                            self.game_state = "menu"
                        else:
                            tree_rect = pygame.Rect(self.tree_offset_x, self.tree_offset_y, 800, 600)
                            if tree_rect.collidepoint(mouse_pos) and (not thumb_rect or not thumb_rect.collidepoint(mouse_pos)):
                                self.tree_dragging = True
                                self.drag_start_x, self.drag_start_y = mouse_pos
                            elif thumb_rect and thumb_rect.collidepoint(mouse_pos):
                                self.scrollbar_dragging = True
                                self.scroll_drag_start_y = mouse_pos[1]
                elif event.type == pygame.MOUSEBUTTONUP:
                    self.tree_dragging = False
                    self.scrollbar_dragging = False
                elif event.type == pygame.MOUSEMOTION:
                    mouse_pos = pygame.mouse.get_pos()
                    if self.tree_dragging:
                        dx = mouse_pos[0] - self.drag_start_x
                        dy = mouse_pos[1] - self.drag_start_y
                        self.tree_offset_x += dx
                        self.tree_offset_y += dy
                        self.drag_start_x, self.drag_start_y = mouse_pos
                    elif self.scrollbar_dragging:
                        mouse_y = event.pos[1]
                        tree_height = self.tree_surface.get_height()
                        view_height = 600
                        max_scroll = tree_height - view_height
                        if max_scroll > 0:
                            scroll_sensitivity = 2.0
                            delta_y = (mouse_y - self.scroll_drag_start_y) * scroll_sensitivity
                            self.scroll_offset = max(0, min(max_scroll, self.scroll_offset + delta_y))
                            self.scroll_drag_start_y = mouse_y
                elif event.type == pygame.MOUSEWHEEL and self.game_state in ["playing", "game_over"]:
                    tree_height = self.tree_surface.get_height()
                    view_height = 600
                    max_scroll = tree_height - view_height
                    scroll_speed = 100
                    self.scroll_offset = max(0, min(max_scroll, self.scroll_offset - event.y * scroll_speed))
                elif event.type == pygame.KEYDOWN:
                    if self.game_state == "input":
                        if event.key == pygame.K_BACKSPACE:
                            if self.active_field == "n":
                                self.input_n = self.input_n[:-1]
                            elif self.active_field == "p1":
                                self.input_player1 = self.input_player1[:-1]
                            elif self.active_field == "p2":
                                self.input_player2 = self.input_player2[:-1]
                        elif event.key == pygame.K_RETURN and self.active_field:
                            self.active_field = None
                        elif self.active_field:
                            char = event.unicode
                            if self.active_field == "n" and char.isdigit():
                                self.input_n += char
                            elif self.active_field == "p1" and char in self.alphabet and (self.n is None or len(self.input_player1) < int(self.input_n or 20)):
                                self.input_player1 += char
                            elif self.active_field == "p2" and char in self.alphabet and (self.n is None or len(self.input_player2) < int(self.input_n or 20)):
                                self.input_player2 += char
                    elif self.game_state in ["playing", "game_over"]:
                        tree_height = self.tree_surface.get_height()
                        view_height = 600
                        max_scroll = tree_height - view_height
                        scroll_speed = 50
                        if event.key == pygame.K_UP:
                            self.scroll_offset = max(0, self.scroll_offset - scroll_speed)
                        elif event.key == pygame.K_DOWN:
                            self.scroll_offset = min(max_scroll, self.scroll_offset + scroll_speed)

            if self.game_state == "menu":
                auto_button, manual_button = self.draw_menu()
            elif self.game_state == "input":
                n_rect, p1_rect, p2_rect, start_button = self.draw_manual_input()
            elif self.game_state == "playing":
                if self.mode == "manual":
                    input_player1 = self.input_player1
                    input_player2 = self.input_player2
                else:
                    input_player1 = self.generate_random_input(self.n)
                    input_player2 = self.generate_random_input(self.n)
                
                base_path = "/Volumes/Datos/Temportales1/"
                all_p1_path = os.path.join(base_path, 'all_paths_player1.txt')
                all_p2_path = os.path.join(base_path, 'all_paths_player2.txt')
                win_p1_path = os.path.join(base_path, 'winning_paths_player1.txt')
                win_p2_path = os.path.join(base_path, 'winning_paths_player2.txt')

                future_all_p1 = self.executor.submit(self.generate_all_combinations_batch, self.start_state_player1, self.n, input_player1, all_p1_path)
                future_all_p2 = self.executor.submit(self.generate_all_combinations_batch, self.start_state_player2, self.n, input_player2, all_p2_path)
                future_all_p1.result()
                future_all_p2.result()

                future_win_p1 = self.executor.submit(self.generate_winning_paths, self.start_state_player1, self.transitions, self.n, input_player1, win_p1_path, self.win_state_player1)
                future_win_p2 = self.executor.submit(self.generate_winning_paths, self.start_state_player2, self.transitions, self.n, input_player2, win_p2_path, self.win_state_player2)
                future_win_p1.result()
                future_win_p2.result()

                all_paths_player1 = self.load_paths_from_file(all_p1_path)
                all_paths_player2 = self.load_paths_from_file(all_p2_path)
                winning_paths_player1 = self.load_paths_from_file(win_p1_path)
                winning_paths_player2 = self.load_paths_from_file(win_p2_path)

                if not winning_paths_player1:
                    self.error_message = f"No hay camino ganador para Jugador 1 con cadena '{input_player1}'"
                    self.game_state = "error"
                    continue
                if not winning_paths_player2:
                    self.error_message = f"No hay camino ganador para Jugador 2 con cadena '{input_player2}'"
                    self.game_state = "error"
                    continue

                selected_path_player1 = random.choice(winning_paths_player1)
                selected_path_player2 = random.choice(winning_paths_player2)

                current_state_player1 = self.start_state_player1
                current_state_player2 = self.start_state_player2
                moves_player1 = 0
                moves_player2 = 0
                turn = self.player1_turn
                player1_history = [current_state_player1]
                player2_history = [current_state_player2]

                print(f"Jugador inicial: {'Jugador 1' if turn else 'Jugador 2'}")
                print(f"Camino inicial P1: {' -> '.join(selected_path_player1)}")
                print(f"Camino inicial P2: {' -> '.join(selected_path_player2)}")
                print(f"Cadena P1: {input_player1}")
                print(f"Cadena P2: {input_player2}")

                thumb_rect, play_again_button = self.render_game_state(current_state_player1, current_state_player2, moves_player1, moves_player2, player1_history, player2_history, all_paths_player1, all_paths_player2, turn)
                pygame.time.wait(1000)

                while not self.game_over and (moves_player1 < self.n or moves_player2 < self.n):
                    if turn and moves_player1 < self.n:
                        if self.player1_paused:
                            print("P1 retomando después de pausa.")
                            new_path = self.select_valid_path(current_state_player1, current_state_player2, winning_paths_player1, moves_player1, input_player1)
                            if new_path:
                                selected_path_player1 = new_path
                                print(f"Nuevo camino P1: {' -> '.join(selected_path_player1)}")
                                current_state_player1 = selected_path_player1[moves_player1 + 1]
                                moves_player1 += 1
                                player1_history.append(current_state_player1)
                            else:
                                print("P1 no tiene caminos válidos desde aquí. Esperando...")
                            self.player1_paused = False
                        else:
                            next_state = selected_path_player1[moves_player1 + 1]
                            if next_state == current_state_player2:
                                print(f"Conflicto: P1 -> {next_state}, ocupado por P2. P1 pausado por un turno.")
                                self.player1_paused = True
                            else:
                                current_state_player1 = next_state
                                player1_history.append(current_state_player1)
                                moves_player1 += 1
                        turn = False
                    elif not turn and moves_player2 < self.n:
                        if self.player2_paused:
                            print("P2 retomando después de pausa.")
                            new_path = self.select_valid_path(current_state_player2, current_state_player1, winning_paths_player2, moves_player2, input_player2)
                            if new_path:
                                selected_path_player2 = new_path
                                print(f"Nuevo camino P2: {' -> '.join(selected_path_player2)}")
                                current_state_player2 = selected_path_player2[moves_player2 + 1]
                                moves_player2 += 1
                                player2_history.append(current_state_player2)
                            else:
                                print("P2 no tiene caminos válidos desde aquí. Esperando...")
                            self.player2_paused = False
                        else:
                            next_state = selected_path_player2[moves_player2 + 1]
                            if next_state == current_state_player1:
                                print(f"Conflicto: P2 -> {next_state}, ocupado por P1. P2 pausado por un turno.")
                                self.player2_paused = True
                            else:
                                current_state_player2 = next_state
                                player2_history.append(current_state_player2)
                                moves_player2 += 1
                        turn = True

                    thumb_rect, play_again_button = self.render_game_state(current_state_player1, current_state_player2, moves_player1, moves_player2, player1_history, player2_history, all_paths_player1, all_paths_player2, turn)
                    pygame.time.wait(1000)
                    print(f"P1: {current_state_player1} ({moves_player1}/{self.n}), P2: {current_state_player2} ({moves_player2}/{self.n})")
                    self.check_winner(current_state_player1, current_state_player2, moves_player1, moves_player2)

                if self.game_over:
                    thumb_rect, play_again_button = self.render_game_state(current_state_player1, current_state_player2, moves_player1, moves_player2, player1_history, player2_history, all_paths_player1, all_paths_player2, turn)
                    self.game_state = "game_over"

            elif self.game_state == "error":
                play_again_button = self.draw_error_message()
                thumb_rect = None

            elif self.game_state == "game_over":
                thumb_rect, play_again_button = self.render_game_state(current_state_player1, current_state_player2, moves_player1, moves_player2, player1_history, player2_history, all_paths_player1, all_paths_player2, turn)

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()
        self.executor.shutdown()
        result = "Empate - Ambos ganan" if self.winner == "Ambos jugadores" else \
                 f"{self.winner} gana" if self.winner else \
                 f"Nadie gana - P1: {current_state_player1}, P2: {current_state_player2}"
        return f"Resultado: {result}"

    def check_winner(self, current_state_player1, current_state_player2, moves_player1, moves_player2):
        player1_wins = current_state_player1 == self.win_state_player1 and moves_player1 == self.n
        player2_wins = current_state_player2 == self.win_state_player2 and moves_player2 == self.n
        
        if player1_wins and player2_wins:
            self.winner = "Ambos jugadores"
            self.game_over = True
        elif player1_wins:
            self.winner = "Jugador 1"
            self.game_over = True
        elif player2_wins:
            self.winner = "Jugador 2"
            self.game_over = True

def setup_and_play():
    game = NFAGame()
    result = game.process_game_with_visualization()
    print(result)

if __name__ == "__main__":
    setup_and_play()