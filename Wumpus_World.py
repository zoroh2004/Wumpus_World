from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import random

app = Flask(__name__)
CORS(app)


# ============ RESOLUTION ENGINE ============
class ResolutionEngine:
    def __init__(self):
        self.inference_steps = 0

    def resolution(self, KB, query):
        self.inference_steps = 0

        if query.startswith("~"):
            negated_query = query[1:]
        else:
            negated_query = f"~{query}"

        clauses = self.to_cnf(KB + [[negated_query]])

        new_clauses = []
        max_iterations = 100

        for iteration in range(max_iterations):
            n = len(clauses)
            pairs = [(clauses[i], clauses[j])
                     for i in range(n) for j in range(i + 1, n)]

            for ci, cj in pairs:
                self.inference_steps += 1
                resolvents = self.resolve(ci, cj)

                if [] in resolvents:
                    return True, self.inference_steps

                for resolvent in resolvents:
                    if resolvent not in clauses and resolvent not in new_clauses:
                        new_clauses.append(resolvent)

            if not new_clauses:
                return False, self.inference_steps

            for clause in new_clauses:
                if clause not in clauses:
                    clauses.append(clause)
            new_clauses = []

        return False, self.inference_steps

    def resolve(self, c1, c2):
        resolutions = []

        for literal in c1:
            if literal.startswith("~"):
                complementary = literal[1:]
            else:
                complementary = f"~{literal}"

            if complementary in c2:
                resolvent = [l for l in c1 if l != literal] + [l for l in c2 if l != complementary]
                resolvent = list(set(resolvent))
                if resolvent:
                    resolutions.append(resolvent)

        return resolutions

    def to_cnf(self, clauses):
        cnf_clauses = []
        for clause in clauses:
            cleaned = list(set(clause))
            if cleaned and cleaned not in cnf_clauses:
                cnf_clauses.append(cleaned)
        return cnf_clauses


# ============ KNOWLEDGE BASE ============
class KnowledgeBase:
    def __init__(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self.clauses = []
        self.engine = ResolutionEngine()

        # Start cell is safe
        self.clauses.append(["~P_0_0"])
        self.clauses.append(["~W_0_0"])

    def tell_percepts(self, x, y, percepts):
        has_breeze = 'breeze' in percepts
        has_stench = 'stench' in percepts

        if has_breeze:
            self.clauses.append([f"B_{x}_{y}"])
            self.add_breeze_rule(x, y)
        else:
            self.clauses.append([f"~B_{x}_{y}"])
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.rows and 0 <= ny < self.cols:
                    self.clauses.append([f"~P_{nx}_{ny}"])

        if has_stench:
            self.clauses.append([f"S_{x}_{y}"])
            self.add_stench_rule(x, y)
        else:
            self.clauses.append([f"~S_{x}_{y}"])
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.rows and 0 <= ny < self.cols:
                    self.clauses.append([f"~W_{nx}_{ny}"])

    def add_breeze_rule(self, x, y):
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.rows and 0 <= ny < self.cols:
                adjacent.append(f"P_{nx}_{ny}")

        if adjacent:
            clause = [f"~B_{x}_{y}"] + adjacent
            self.clauses.append(clause)
            for pit in adjacent:
                self.clauses.append([f"~{pit}", f"B_{x}_{y}"])

    def add_stench_rule(self, x, y):
        adjacent = []
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.rows and 0 <= ny < self.cols:
                adjacent.append(f"W_{nx}_{ny}")

        if adjacent:
            clause = [f"~S_{x}_{y}"] + adjacent
            self.clauses.append(clause)
            for wumpus in adjacent:
                self.clauses.append([f"~{wumpus}", f"S_{x}_{y}"])

    def query_safety(self, x, y):
        query_not_pit = f"~P_{x}_{y}"
        query_not_wumpus = f"~W_{x}_{y}"

        result_pit, steps_pit = self.engine.resolution(self.clauses, query_not_pit)
        result_wumpus, steps_wumpus = self.engine.resolution(self.clauses, query_not_wumpus)

        is_safe = result_pit and result_wumpus
        return is_safe, (steps_pit + steps_wumpus)


# ============ WUMPUS WORLD ============
class WumpusWorld:
    def __init__(self, rows, cols, num_pits):
        self.rows = rows
        self.cols = cols
        self.grid = []
        self.agent_visited = set()
        self._create_grid()
        self._place_hazards(num_pits)

    def _create_grid(self):
        for i in range(self.rows):
            row = []
            for j in range(self.cols):
                cell = {
                    'pit': False,
                    'wumpus': False,
                    'gold': False,
                    'breeze': False,
                    'stench': False,
                    'visited': False
                }
                row.append(cell)
            self.grid.append(row)

    def _place_hazards(self, num_pits):
        # Place pits
        available = [(i, j) for i in range(self.rows)
                     for j in range(self.cols) if (i, j) != (0, 0)]

        actual_pits = min(num_pits, len(available))
        if actual_pits > 0:
            pit_positions = random.sample(available, actual_pits)

            for x, y in pit_positions:
                self.grid[x][y]['pit'] = True
                for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.rows and 0 <= ny < self.cols:
                        self.grid[nx][ny]['breeze'] = True

        # Place Wumpus
        available = [(i, j) for i in range(self.rows)
                     for j in range(self.cols)
                     if (i, j) != (0, 0) and not self.grid[i][j]['pit']]

        if available:
            wumpus_pos = random.choice(available)
            x, y = wumpus_pos
            self.grid[x][y]['wumpus'] = True
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.rows and 0 <= ny < self.cols:
                    self.grid[nx][ny]['stench'] = True

        # Place gold
        available = [(i, j) for i in range(self.rows)
                     for j in range(self.cols)
                     if (i, j) != (0, 0)
                     and not self.grid[i][j]['pit']
                     and not self.grid[i][j]['wumpus']]

        if available:
            gold_pos = random.choice(available)
            self.grid[gold_pos[0]][gold_pos[1]]['gold'] = True

    def get_percepts(self, x, y):
        cell = self.grid[x][y]
        percepts = []
        if cell['breeze']:
            percepts.append('breeze')
        if cell['stench']:
            percepts.append('stench')
        if cell['gold']:
            percepts.append('glitter')
        return percepts

    def get_visible_grid(self):
        visible = []
        for i in range(self.rows):
            row = []
            for j in range(self.cols):
                cell_data = {
                    'pit': False,
                    'wumpus': False,
                    'gold': False,
                    'breeze': False,
                    'stench': False,
                    'visited': False
                }

                if (i, j) in self.agent_visited:
                    original = self.grid[i][j]
                    cell_data['pit'] = original['pit']
                    cell_data['wumpus'] = original['wumpus']
                    cell_data['gold'] = original['gold']
                    cell_data['breeze'] = original['breeze']
                    cell_data['stench'] = original['stench']
                    cell_data['visited'] = True

                row.append(cell_data)
            visible.append(row)
        return visible

    def get_full_grid(self):
        full = []
        for i in range(self.rows):
            row = []
            for j in range(self.cols):
                cell = self.grid[i][j].copy()
                cell['visited'] = True
                row.append(cell)
            full.append(row)
        return full


# Store games
games = {}

# ============ HTML TEMPLATE ============
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wumpus World Agent</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: Arial, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 20px; 
            padding: 30px; 
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 { text-align: center; color: #333; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #666; margin-bottom: 30px; }
        .setup { 
            background: #f5f5f5; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            flex-wrap: wrap;
        }
        .setup input { 
            width: 60px; 
            padding: 8px; 
            border: 2px solid #667eea; 
            border-radius: 5px; 
            margin-left: 5px;
        }
        .setup button { 
            padding: 12px 30px; 
            background: #667eea; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer;
            font-size: 1.1em;
        }
        .setup button:hover { background: #764ba2; }
        .game-area { display: flex; gap: 30px; margin-bottom: 30px; }
        #grid-container { 
            flex: 1;
            display: grid;
            gap: 3px;
            background: #333;
            padding: 3px;
            border-radius: 8px;
            min-height: 400px;
        }
        .cell {
            aspect-ratio: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2em;
            border-radius: 5px;
            min-width: 80px;
            min-height: 80px;
            transition: all 0.3s;
        }
        .unknown { background: #b0b0b0; }
        .safe { background: #90EE90; }
        .danger { background: #FF6B6B; }
        .agent { 
            background: #FFD700; 
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.7);
        }
        .dashboard {
            width: 300px;
            background: #f5f5f5;
            padding: 20px;
            border-radius: 10px;
        }
        .metric {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            margin-bottom: 15px;
        }
        .metric .label { color: #666; display: block; margin-bottom: 5px; }
        .metric .value { color: #333; font-size: 1.3em; font-weight: bold; display: block; }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        .d-pad {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            margin-bottom: 20px;
        }
        .middle-row { display: flex; gap: 30px; }
        .d-pad button {
            width: 60px;
            height: 60px;
            font-size: 1.8em;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
        }
        .d-pad button:hover { background: #764ba2; }
        .btn-safety {
            width: 100%;
            padding: 15px;
            background: #28a745;
            color: white;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1.1em;
        }
        .btn-safety:hover { background: #218838; }
        #game-messages { min-height: 50px; }
        .legend {
            background: #f5f5f5;
            padding: 20px;
            border-radius: 10px;
            display: flex;
            gap: 30px;
            flex-wrap: wrap;
            align-items: center;
        }
        .legend-item { display: flex; align-items: center; gap: 10px; }
        .color-box {
            width: 25px;
            height: 25px;
            border-radius: 5px;
            border: 2px solid #333;
        }
        .color-box.safe { background: #90EE90; }
        .color-box.unknown { background: #b0b0b0; }
        .color-box.danger { background: #FF6B6B; }
        .color-box.agent { background: #FFD700; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Wumpus World - Knowledge-Based Agent</h1>
        <p class="subtitle">Using Propositional Logic and Resolution Refutation</p>

        <div class="setup">
            <label>Rows: <input type="number" id="rows" value="4" min="3" max="8"></label>
            <label>Columns: <input type="number" id="cols" value="4" min="3" max="8"></label>
            <label>Pits: <input type="number" id="pits" value="2" min="1" max="5"></label>
            <button onclick="startNewGame()">New Game</button>
        </div>

        <div class="game-area">
            <div id="grid-container"></div>

            <div class="dashboard">
                <h2>📊 Metrics Dashboard</h2>
                <div class="metric">
                    <span class="label">Inference Steps:</span>
                    <span class="value" id="inference-steps">0</span>
                </div>
                <div class="metric">
                    <span class="label">Current Percepts:</span>
                    <span class="value" id="current-percepts">None</span>
                </div>
                <div class="metric">
                    <span class="label">Agent Position:</span>
                    <span class="value" id="agent-position">(0, 0)</span>
                </div>
                <div class="metric">
                    <span class="label">KB Size:</span>
                    <span class="value" id="kb-size">0</span>
                </div>

                <div class="controls">
                    <h3>🎮 Controls</h3>
                    <div class="d-pad">
                        <button onclick="move('up')">↑</button>
                        <div class="middle-row">
                            <button onclick="move('left')">←</button>
                            <button onclick="move('right')">→</button>
                        </div>
                        <button onclick="move('down')">↓</button>
                    </div>
                    <button class="btn-safety" onclick="querySafety()">Check Safe Cells</button>
                </div>

                <div id="game-messages"></div>
            </div>
        </div>

        <div class="legend">
            <strong>Legend:</strong>
            <div class="legend-item"><span class="color-box safe"></span> Safe Cell</div>
            <div class="legend-item"><span class="color-box unknown"></span> Unknown/Unvisited</div>
            <div class="legend-item"><span class="color-box danger"></span> Confirmed Hazard</div>
            <div class="legend-item"><span class="color-box agent"></span> Agent Position</div>
        </div>
    </div>

    <script>
        let gameId = null;

        function startNewGame() {
            const rows = parseInt(document.getElementById('rows').value);
            const cols = parseInt(document.getElementById('cols').value);
            const pits = parseInt(document.getElementById('pits').value);

            fetch('/api/new_game', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({rows, cols, num_pits: pits})
            })
            .then(response => response.json())
            .then(data => {
                gameId = data.game_id;
                renderGrid(data.grid, data.agent_pos);
                updateMetrics({
                    steps: data.inference_steps || 0,
                    percepts: data.percepts || [],
                    position: data.agent_pos,
                    kbSize: data.kb_size || 0
                });
                document.getElementById('game-messages').innerHTML = 
                    '<div style="padding: 10px; background: #d4edda; border-radius: 5px; color: #155724;">New game started! Use arrow keys or buttons to move.</div>';
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error starting game');
            });
        }

        function move(direction) {
            if (!gameId) {
                alert('Start a new game first!');
                return;
            }

            fetch('/api/move', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({game_id: gameId, direction})
            })
            .then(response => response.json())
            .then(data => {
                if (data.game_over) {
                    const grid = data.full_grid || data.grid;
                    renderGrid(grid, data.agent_pos);
                    const msgDiv = document.getElementById('game-messages');
                    if (data.won) {
                        msgDiv.innerHTML = '<div style="padding: 20px; background: #d4edda; border-radius: 10px;"><h3>🎉 ' + data.message + '</h3><button onclick="startNewGame()" style="margin-top:10px; padding:10px 20px;">Play Again</button></div>';
                    } else {
                        msgDiv.innerHTML = '<div style="padding: 20px; background: #f8d7da; border-radius: 10px;"><h3>💀 ' + data.message + '</h3><button onclick="startNewGame()" style="margin-top:10px; padding:10px 20px;">Try Again</button></div>';
                    }
                } else {
                    renderGrid(data.grid, data.new_position);
                    updateMetrics({
                        steps: data.inference_steps || 0,
                        percepts: data.percepts || [],
                        position: data.new_position,
                        kbSize: data.kb_size || 0
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error moving agent');
            });
        }

        function querySafety() {
            if (!gameId) {
                alert('Start a new game first!');
                return;
            }

            fetch('/api/get_safe_cells', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({game_id: gameId})
            })
            .then(response => response.json())
            .then(data => {
                if (data.safe_cells) {
                    const cells = document.querySelectorAll('.cell');
                    cells.forEach(cell => {
                        const x = parseInt(cell.dataset.x);
                        const y = parseInt(cell.dataset.y);
                        if (data.safe_cells.some(([sx, sy]) => sx === x && sy === y)) {
                            cell.style.boxShadow = '0 0 15px 5px #00ff00';
                            setTimeout(() => { cell.style.boxShadow = ''; }, 2000);
                        }
                    });
                }
                document.getElementById('inference-steps').textContent = data.inference_steps || 0;
                document.getElementById('kb-size').textContent = data.kb_size || 0;
            })
            .catch(error => console.error('Error:', error));
        }

        function renderGrid(grid, agentPos) {
            const container = document.getElementById('grid-container');
            console.log('Rendering grid:', grid, 'Agent at:', agentPos);

            if (!grid || grid.length === 0) {
                container.innerHTML = '<div style="color:white; padding:20px;">No grid data</div>';
                return;
            }

            const rows = grid.length;
            const cols = grid[0].length;

            container.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
            container.innerHTML = '';

            for (let i = 0; i < rows; i++) {
                for (let j = 0; j < cols; j++) {
                    const cell = document.createElement('div');
                    cell.className = 'cell';
                    cell.dataset.x = i;
                    cell.dataset.y = j;

                    const isAgent = agentPos && agentPos[0] === i && agentPos[1] === j;
                    const cellData = grid[i][j];

                    console.log(`Cell [${i},${j}]:`, cellData);

                    if (isAgent) {
                        cell.className = 'cell agent';
                        cell.textContent = '🤖';
                    } else if (cellData && cellData.visited) {
                        if (cellData.pit) {
                            cell.className = 'cell danger';
                            cell.textContent = '🕳️';
                        } else if (cellData.wumpus) {
                            cell.className = 'cell danger';
                            cell.textContent = '👹';
                        } else {
                            cell.className = 'cell safe';
                            let text = '';
                            if (cellData.breeze) text += '💨';
                            if (cellData.stench) text += '👃';
                            if (cellData.gold) text += '💰';
                            cell.textContent = text || '✓';
                        }
                    } else {
                        cell.className = 'cell unknown';
                        cell.textContent = '❓';
                    }

                    container.appendChild(cell);
                }
            }
        }

        function updateMetrics(data) {
            document.getElementById('inference-steps').textContent = data.steps || 0;
            document.getElementById('current-percepts').textContent = 
                data.percepts.length > 0 ? data.percepts.join(', ') : 'None';
            document.getElementById('agent-position').textContent = 
                `(${data.position[0]}, ${data.position[1]})`;
            document.getElementById('kb-size').textContent = data.kbSize || 0;
        }

        // Keyboard controls
        document.addEventListener('keydown', (e) => {
            switch(e.key) {
                case 'ArrowUp': e.preventDefault(); move('up'); break;
                case 'ArrowDown': e.preventDefault(); move('down'); break;
                case 'ArrowLeft': e.preventDefault(); move('left'); break;
                case 'ArrowRight': e.preventDefault(); move('right'); break;
                case 's': case 'S': e.preventDefault(); querySafety(); break;
            }
        });

        // Start game on load
        window.onload = () => startNewGame();
    </script>
</body>
</html>
'''


# ============ API ROUTES ============
@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/new_game', methods=['POST'])
def new_game():
    try:
        data = request.json
        rows = int(data.get('rows', 4))
        cols = int(data.get('cols', 4))
        num_pits = int(data.get('num_pits', 2))

        game_id = str(len(games))
        world = WumpusWorld(rows, cols, num_pits)
        kb = KnowledgeBase(rows, cols)

        world.agent_visited.add((0, 0))

        games[game_id] = {
            'world': world,
            'kb': kb,
            'agent_pos': (0, 0),
            'visited': set([(0, 0)]),
            'inference_steps': 0,
            'game_over': False,
            'won': False
        }

        initial_percepts = world.get_percepts(0, 0)
        grid = world.get_visible_grid()

        print(f"New game {game_id}: {rows}x{cols} grid, {num_pits} pits")
        print(f"Grid: {grid}")

        return jsonify({
            'game_id': game_id,
            'grid': grid,
            'dimensions': {'rows': rows, 'cols': cols},
            'agent_pos': [0, 0],
            'percepts': initial_percepts,
            'inference_steps': 0,
            'kb_size': len(kb.clauses)
        })
    except Exception as e:
        print(f"Error in new_game: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/move', methods=['POST'])
def move_agent():
    try:
        data = request.json
        game_id = data['game_id']
        direction = data['direction']

        game = games[game_id]
        world = game['world']
        kb = game['kb']

        if game['game_over']:
            return jsonify({'error': 'Game over'}), 400

        x, y = game['agent_pos']
        new_pos = list(game['agent_pos'])

        if direction == 'up' and x > 0:
            new_pos[0] -= 1
        elif direction == 'down' and x < world.rows - 1:
            new_pos[0] += 1
        elif direction == 'left' and y > 0:
            new_pos[1] -= 1
        elif direction == 'right' and y < world.cols - 1:
            new_pos[1] += 1
        else:
            return jsonify({'error': 'Invalid move'}), 400

        new_pos = tuple(new_pos)
        game['agent_pos'] = new_pos
        game['visited'].add(new_pos)
        world.agent_visited.add(new_pos)

        percepts = world.get_percepts(new_pos[0], new_pos[1])
        cell = world.grid[new_pos[0]][new_pos[1]]

        if cell['pit']:
            game['game_over'] = True
            return jsonify({
                'game_over': True, 'won': False,
                'message': 'Agent fell into a pit!',
                'agent_pos': [new_pos[0], new_pos[1]],
                'full_grid': world.get_full_grid(),
                'grid': world.get_visible_grid(),
                'percepts': percepts
            })

        if cell['wumpus']:
            game['game_over'] = True
            return jsonify({
                'game_over': True, 'won': False,
                'message': 'Agent was eaten by the Wumpus!',
                'agent_pos': [new_pos[0], new_pos[1]],
                'full_grid': world.get_full_grid(),
                'grid': world.get_visible_grid(),
                'percepts': percepts
            })

        if cell['gold']:
            game['game_over'] = True
            game['won'] = True
            return jsonify({
                'game_over': True, 'won': True,
                'message': 'You found the gold! You win!',
                'agent_pos': [new_pos[0], new_pos[1]],
                'full_grid': world.get_full_grid(),
                'grid': world.get_visible_grid(),
                'percepts': percepts
            })

        kb.tell_percepts(new_pos[0], new_pos[1], percepts)
        grid = world.get_visible_grid()

        print(f"Move to {new_pos}, grid: {grid}")

        return jsonify({
            'game_over': False,
            'new_position': [new_pos[0], new_pos[1]],
            'percepts': percepts,
            'grid': grid,
            'inference_steps': game.get('inference_steps', 0),
            'kb_size': len(kb.clauses)
        })
    except Exception as e:
        print(f"Error in move: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/get_safe_cells', methods=['POST'])
def get_safe_cells():
    try:
        data = request.json
        game_id = data['game_id']

        game = games[game_id]
        kb = game['kb']
        world = game['world']
        agent_pos = game['agent_pos']

        x, y = agent_pos
        adjacent = []
        if x > 0: adjacent.append([x - 1, y])
        if x < world.rows - 1: adjacent.append([x + 1, y])
        if y > 0: adjacent.append([x, y - 1])
        if y < world.cols - 1: adjacent.append([x, y + 1])

        safe_cells = []
        total_steps = 0

        for cell in adjacent:
            if tuple(cell) not in game['visited']:
                is_safe, steps = kb.query_safety(cell[0], cell[1])
                total_steps += steps
                if is_safe:
                    safe_cells.append(cell)

        game['inference_steps'] = game.get('inference_steps', 0) + total_steps

        return jsonify({
            'safe_cells': safe_cells,
            'inference_steps': game['inference_steps'],
            'kb_size': len(kb.clauses)
        })
    except Exception as e:
        print(f"Error in get_safe_cells: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("Starting Wumpus World server...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, host='0.0.0.0', port=5000)
