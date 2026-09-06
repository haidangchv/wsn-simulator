# WSN Simulator Specification

Version: 0.5.0

## 1. Objective

Develop a modular, high-performance Wireless Sensor Network (WSN) simulator for studying:

- Multi-hop communication from sensor nodes to a central sink node
- Minimum-hop routing and dynamic topology adaptation
- Energy-Constrained Minimum-Hop Routing (ECMHR)
- First-order radio energy consumption modeling
- Network lifetime evaluation (FND, HND, LND)
- Sensor data generation and transmission
- Data compression and encryption
- Fake sensor and fake data detection
- Battery exhaustion attack prevention
- Clustering and edge processing
- Interactive web-based visualization and telemetry

---

## 2. Simulation Area

The simulated area is a rectangular region:

- Width: 2000 meters
- Height: 2000 meters

Coordinate system:

- $0 \le x \le 2000\text{ m}$
- $0 \le y \le 2000\text{ m}$

---

## 3. Sensor Network Deployment

Total number of sensor nodes:

- **500 nodes**, randomly deployed uniformly over the simulation area with a fixed random seed (default: `42`).

Each sensor data structure contains:

- Unique ID (`node_id`: $1 \dots 500$)
- Spatial coordinates (`x`, `y`)
- Sensor type (`sensor_type`)
- Battery specifications (`initial_energy`, `remaining_energy`, `consumed_energy_j`)
- Communication parameters (`transmission_range`, `neighbors`)
- Node state (`state`: `ALIVE`, `LOW_ENERGY`, `DEAD`)
- Relay capability flag (`relay_enabled`)
- Telemetry counters (`generated_packets`, `sent_packets`, `received_packets`, `forwarded_packets`)

---

## 4. Sensor Types

The network contains five heterogeneous environmental sensor types:

- 100 Temperature sensors
- 100 Humidity sensors
- 100 PM2.5 air-quality sensors
- 100 Wind sensors
- 100 Water-quality sensors

Total: **500 nodes**

---

## 5. Sink Node

Default sink position:

- $x = 1000\text{ m}$
- $y = 1000\text{ m}$
- `node_id = "SINK"`

The sink is assumed to have unlimited power and processing capabilities.

---

## 6. Energy Model

### 6.1 Battery Parameters
- Initial energy ($E_0$): **2.0 Joules** per sensor node
- Low-energy threshold ratio: **20%** of initial energy ($E_{threshold} = 0.4\text{ J}$)

### 6.2 Node States
- `ALIVE`: $E_{remaining} / E_0 > 0.20$
- `LOW_ENERGY`: $0 < E_{remaining} / E_0 \le 0.20$ (In baseline routing, remains a relay; in ECMHR, avoided as relay)
- `DEAD`: $E_{remaining} \le 0$ (Node cannot generate packets or act as a relay; excluded from active routing graph)

### 6.3 Radio Model Equations (Heinzelman First-Order Model)
The radio model defines energy dissipation for transmitting ($E_{TX}$) and receiving ($E_{RX}$) a packet of $k$ bits over distance $d$:

$$d_0 = \sqrt{\frac{\epsilon_{fs}}{\epsilon_{mp}}} = \sqrt{\frac{10 \times 10^{-12}}{0.0013 \times 10^{-12}}} \approx 87.7\text{ m}$$

- **Transmission Energy ($E_{TX}$)**:
  $$E_{TX}(k, d) = \begin{cases} 
  k \cdot E_{elec} + k \cdot \epsilon_{fs} \cdot d^2 & \text{if } d < d_0 \\ 
  k \cdot E_{elec} + k \cdot \epsilon_{mp} \cdot d^4 & \text{if } d \ge d_0 
  \end{cases}$$

- **Reception Energy ($E_{RX}$)**:
  $$E_{RX}(k) = k \cdot E_{elec}$$

Parameters:
- $E_{elec} = 50\text{ nJ/bit}$
- $\epsilon_{fs} = 10\text{ pJ/bit/m}^2$
- $\epsilon_{mp} = 0.0013\text{ pJ/bit/m}^4$

---

## 7. Communication & Neighbor Graph

- Default transmission range ($R$): **200 meters**
- Communication graph: Undirected geometric random graph $G = (V, E)$, where an edge $(u, v)$ exists if and only if:
  $$\text{dist}(u, v) \le R$$
- Graph analytics computed:
  - Average node degree
  - Number of edges
  - Connected sensors to sink
  - Isolated sensors
  - Direct sink neighbors
  - Connectivity ratio: $N_{connected} / N_{total}$

---

## 8. Packet Specification

- Payload size: **128 bytes** (1024 bits)
- Sampling interval: **10 seconds** per round
- Per-hop processing delay: **10 ms**
- Packet fields:
  - `source_id`: Originating sensor ID
  - `sequence_number`: Monotonically increasing sequence number per sensor
  - `sensor_type`: Sensor telemetry category
  - `payload_size_bytes`: Size in bytes
  - `created_round`: Round number when generated
  - `route`: List of node IDs representing the transmission path
  - `hop_count`: Total hops from source to sink
  - `delivered`: Delivery success boolean
  - `delay_ms`: End-to-end delay ($h \times 10\text{ ms}$)
  - `dropped_reason`: Reason if dropped (`SOURCE_DEAD`, `NO_ROUTE`, `TX_ENERGY_INSUFFICIENT`, `RX_ENERGY_INSUFFICIENT`)

---

## 9. Simulation Execution Model

The simulator operates on a discrete, round-based execution model:

### Round Execution Steps:
1. **Snapshot Alive Nodes**: Determine active nodes at round start.
2. **Sequential Packet Generation & Routing**: For each alive sensor:
   - Packet created with current sequence number.
   - Build active graph $G_{active}$ by excluding all nodes with $E_{remaining} \le 0$.
   - Compute minimum-hop shortest path to Sink via BFS / Dijkstra.
   - For each hop $(u, v)$ along the path:
     - Check and deduct transmission energy from sender $u$.
     - Check and deduct reception energy from receiver $v$.
     - If energy is insufficient, packet is marked dropped and transmission halts.
   - Upon reaching Sink, packet marked delivered; delay, hop count, and sink byte counters updated.
3. **Update Network Lifetime Metrics**:
   - Check and record `FND` (First Node Dead round).
   - Check and record `HND` (Half Nodes Dead round: $\ge 250$ dead).
   - Check and record `LND` (Last Node Dead round: 500 dead).
4. **Record Round History**: Snapshot of all cumulative metrics appended to `simulator.history`.

---

## 10. Routing Protocols

1. **Baseline Minimum-Hop Routing (Implemented)**:
   - Shortest path calculated using hop count as weight.
   - Dynamic rerouting: Dead nodes are excluded on each round.
2. **Energy-Constrained Minimum-Hop Routing (ECMHR - In Progress)**:
   - Prefers minimum hops while avoiding nodes in `LOW_ENERGY` state as relays.
   - Tie-breaking based on maximal residual energy.

---

## 11. Metrics & Performance Indicators

The simulator computes and tracks the following metrics:

| Metric | Formula / Definition | Unit |
| :--- | :--- | :--- |
| **PDR** (Packet Delivery Ratio) | $P_{delivered} / P_{generated}$ | $\%$ |
| **Throughput** | $(\text{Delivered Bytes} \times 8) / T_{elapsed}$ | kbps |
| **Average Delay** | $\sum \text{delay}_{delivered} / P_{delivered}$ | ms |
| **Average Hop Count** | $\sum \text{hops}_{delivered} / P_{delivered}$ | hops |
| **Energy Consumed** | Total energy dissipated across all nodes | Joules |
| **Residual Energy** | Total remaining battery across all nodes | Joules |
| **Energy Efficiency** | $(\text{Delivered Bytes} \times 8) / \text{Energy Consumed}$ | bit/J |
| **FND** | Round index where first node died | round |
| **HND** | Round index where $\ge 50\%$ of nodes died | round |
| **LND** | Round index where $100\%$ of nodes died | round |

---

## 12. Evaluation, Export & Interactive GUI

- **Data Export (`metrics/evaluator.py`)**:
  - `round_history.csv`: Cumulative metrics for every simulated round.
  - `node_results.csv`: Per-node status, location, remaining energy, and traffic counts.
  - `summary.csv`: Overall simulation final summary.
- **Plotting (`visualization/`)**:
  - Network lifetime curves (Alive nodes vs. Round).
  - Residual energy decay curve.
  - PDR and throughput vs. Round.
  - Routing hop-count distribution histograms.
- **Streamlit Interactive Web UI (`app.py`)**:
  - Interactive Plotly WebGL network graph with route inspection excluding dead nodes.
  - Configurable parameters (area, seed, range, initial energy, threshold).
  - Multi-round run triggers with spinner indicators.
  - Network survival progress bar, live metrics, packet statistics, and detailed node inspector table.