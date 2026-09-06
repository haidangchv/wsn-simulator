# Wireless Sensor Network (WSN) Simulator

A modular, high-performance, round-based Wireless Sensor Network (WSN) simulator developed in Python. Designed for researching multi-hop communications, minimum-hop and energy-aware routing protocols, radio energy consumption models, network lifetime evaluation, and security mechanisms.

Includes an interactive **Streamlit** dashboard with **Plotly WebGL** topology visualization.

---

## Key Features

- **Realistic Deployment & Heterogeneous Sensors**:
  - Simulates an area of $2000 \times 2000\text{ m}$ with 500 randomly deployed sensor nodes and 1 centrally located Sink node $(1000, 1000)$.
  - 5 sensor types: Temperature, Humidity, PM2.5, Wind, and Water Quality (100 nodes each).
- **Geometric Neighbor Graph & Topology Analysis**:
  - Distance-based communication graph with configurable transmission range ($R = 200\text{ m}$).
  - Computes connectivity ratio, direct sink neighbors, isolated nodes, and average node degree.
- **Dynamic Minimum-Hop Routing**:
  - BFS / Dijkstra shortest-path route discovery to the Sink.
  - Active graph pruning: routes dynamically bypass dead nodes (`DEAD`).
- **First-Order Radio Energy Model (Heinzelman Model)**:
  - Free-space ($\epsilon_{fs}$) and multipath fading ($\epsilon_{mp}$) propagation models with threshold distance $d_0 = \sqrt{\epsilon_{fs} / \epsilon_{mp}}$.
  - Tracks transmission ($E_{TX}$) and reception ($E_{RX}$) energy per packet.
  - Dynamic battery depletion and state transitions: `ALIVE`, `LOW_ENERGY` (threshold $\le 20\%$), and `DEAD` ($E \le 0$).
- **Round-Based Discrete Event Simulation Engine**:
  - `WSNSimulator` simulates packet generation, multi-hop forwarding, relay reception, and delivery to Sink.
  - Measures Packet Delivery Ratio (PDR), Sink Throughput (kbps), Average End-to-End Delay (ms), Average Hop Count, Total Energy Consumed, and Residual Energy.
  - Network lifetime tracking: **FND** (First Node Dead), **HND** (Half Nodes Dead), and **LND** (Last Node Dead).
  - Maintains a round-by-round cumulative history snapshot.
- **Metrics Evaluation & CSV Export**:
  - Automatically exports simulation results to CSV: `round_history.csv`, `node_results.csv`, and `summary.csv`.
- **Publication-Ready Visualizations**:
  - Matplotlib generation for Network Lifetime, Residual Energy, PDR, and Throughput curves.
- **Interactive Streamlit Web Dashboard**:
  - Live topology map powered by Plotly WebGL with interactive route tracing.
  - Real-time simulation controls (Run 1, 10, 50, or Custom rounds) with progress spinners.
  - Visual Network Survival progress bar, Packet Statistics cards, and per-node inspector table.

---

## Project Structure

```text
wsn-simulator/
│
├── app.py                          # Streamlit interactive web application
├── main.py                         # Baseline topology & routing inspection script
├── run_simulation.py               # Long-run simulation script with CSV & plot export
├── run_energy_demo.py              # Energy and single/multi-round verification demo
├── config.yaml                     # Central system configuration
├── SPECIFICATION.md                # System engineering specification
├── requirements.txt                # Project dependencies
│
├── core/                           # Core network entities
│   ├── network.py                  # WirelessSensorNetwork manager & graph analytics
│   ├── sensor.py                   # SensorNode model & battery states
│   ├── sink.py                     # SinkNode model
│   └── packet.py                   # Packet data structure & metadata
│
├── topology/                       # Network deployment
│   └── deployment.py               # Random sensor & sink placement
│
├── routing/                        # Routing protocols
│   └── minimum_hop.py              # Minimum-hop shortest path algorithm
│
├── energy/                         # Energy dissipation models
│   └── radio_model.py              # First-order radio energy model (Heinzelman)
│
├── simulation/                     # Simulation execution engine
│   └── simulator.py                # WSNSimulator (round-based multi-hop execution)
│
├── metrics/                        # Metrics evaluation & export
│   └── evaluator.py                # DataFrame conversion & CSV export
│
├── visualization/                  # Matplotlib plotting utilities
│   ├── topology.py                 # Topology & route plotting
│   ├── routing.py                  # Hop-count distribution plots
│   └── energy.py                   # Lifetime, PDR, and energy curves
│
├── streamlit_components/           # Streamlit UI modules
│   └── network_chart.py            # Plotly interactive network chart
│
└── tests/                          # Automated unit test suite (pytest)
    ├── test_deployment.py          # Deployment tests
    ├── test_neighbor_graph.py      # Topology & neighbor graph tests
    ├── test_minimum_hop.py         # Minimum-hop routing tests
    ├── test_radio_model.py         # Energy consumption tests
    └── test_simulator_metrics.py   # Simulation engine & metrics tests
```

---

## Configuration (`config.yaml`)

Key simulation parameters are centralized in `config.yaml`:

```yaml
network:
  width_m: 2000
  height_m: 2000
  num_sensors: 500
  random_seed: 42

sink:
  x: 1000
  y: 1000

energy:
  e_elec_nj_per_bit: 50         # Transmitter / Receiver electronics energy
  eps_fs_pj_per_bit_m2: 10       # Free space amplifier energy
  eps_mp_pj_per_bit_m4: 0.0013   # Multipath amplifier energy
  per_hop_delay_ms: 10           # Processing delay per hop

sensor:
  initial_energy_j: 2.0          # Battery capacity (Joules)
  transmission_range_m: 200      # Communication radius (m)
  energy_threshold_ratio: 0.20   # 20% threshold for LOW_ENERGY state

packet:
  payload_size_bytes: 128        # Packet payload size
  sampling_interval_seconds: 10  # Time between rounds (1 round = 10s)

simulation:
  mode: "round_based"
  max_rounds: 10000
```

---

## Installation & Setup

### 1. Clone the repository & create a virtual environment
```bash
git clone https://github.com/haidangchv/wsn-simulator.git
cd wsn-simulator

python -m venv .venv
# On Windows PowerShell:
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Application

### Launch the Streamlit Interactive Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501` to access:
- **Interactive Network Graph**: Inspect sensor positions, connectivity, and active routes.
- **Simulation Controls**: Run 1, 10, 50, or custom simulation rounds.
- **Real-time Telemetry**: Live updates of PDR, throughput, delay, remaining energy, and network survival.
- **Sensor Inspector**: Sort and filter all 500 nodes by residual energy, state, packets sent/received/forwarded.

---

### Run Automated Unit Tests
```bash
pytest
```
Currently passes **33 automated unit tests** across 5 test suites.

---

### Command-Line Demos & Simulations

1. **Topology & Routing Inspection**:
   ```bash
   python main.py
   ```
2. **Energy Model & FND Demonstration**:
   ```bash
   python run_energy_demo.py
   ```
3. **Full Simulation Run with Export**:
   ```bash
   python run_simulation.py
   ```
   Exports results to `outputs/results/` and generates performance figures in `outputs/`.

---

## Development Roadmap

- [x] **Stage 1**: Random sensor deployment & heterogeneous types
- [x] **Stage 2**: Geometric neighbor graph & topology analytics
- [x] **Stage 3**: Minimum-Hop shortest-path routing
- [x] **Stage 4**: First-order radio energy model & battery states
- [x] **Stage 5**: Round-based simulation engine & lifetime metrics (FND, HND, LND)
- [x] **Stage 6**: CSV exports & Matplotlib visualization curves
- [x] **Stage 7**: Streamlit interactive web dashboard with Plotly
- [ ] **Stage 8**: Energy-Constrained Minimum-Hop Routing (ECMHR)
- [ ] **Stage 9**: Data generation, compression & encryption
- [ ] **Stage 10**: Security attack models (battery exhaustion, fake sensor/data) & trust defenses
- [ ] **Stage 11**: Clustering (LEACH / hybrid) & edge processing