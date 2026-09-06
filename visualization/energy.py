from pathlib import Path

import matplotlib.pyplot as plt


def _prepare_output():

    output_dir = Path(
        "outputs"
    )

    output_dir.mkdir(
        exist_ok=True
    )

    return output_dir


def plot_alive_nodes(
    history,
    show=True,
    save=True
):

    if not history:
        return

    rounds = [
        row["round"]
        for row in history
    ]

    alive = [
        row["alive_nodes"]
        for row in history
    ]

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    ax.plot(
        rounds,
        alive
    )

    ax.set_xlabel(
        "Round"
    )

    ax.set_ylabel(
        "Alive Sensor Nodes"
    )

    ax.set_title(
        "Network Lifetime"
    )

    ax.grid(
        True,
        alpha=0.25
    )

    plt.tight_layout()

    if save:

        path = (
            _prepare_output()
            / "alive_nodes_vs_round.png"
        )

        plt.savefig(
            path,
            dpi=200
        )

    if show:
        plt.show()

    else:
        plt.close(fig)

def plot_remaining_energy(
    history,
    show=True,
    save=True
):

    if not history:
        return

    rounds = [
        row["round"]
        for row in history
    ]

    energy = [
        row["total_remaining_energy_j"]
        for row in history
    ]

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    ax.plot(
        rounds,
        energy
    )

    ax.set_xlabel(
        "Round"
    )

    ax.set_ylabel(
        "Total Remaining Energy (J)"
    )

    ax.set_title(
        "Network Residual Energy"
    )

    ax.grid(
        True,
        alpha=0.25
    )

    plt.tight_layout()

    if save:

        path = (
            _prepare_output()
            / "remaining_energy_vs_round.png"
        )

        plt.savefig(
            path,
            dpi=200
        )

    if show:
        plt.show()

    else:
        plt.close(fig)

def plot_pdr(
    history,
    show=True,
    save=True
):

    if not history:
        return

    rounds = [
        row["round"]
        for row in history
    ]

    pdr = [
        row["pdr"] * 100
        for row in history
    ]

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    ax.plot(
        rounds,
        pdr
    )

    ax.set_xlabel(
        "Round"
    )

    ax.set_ylabel(
        "PDR (%)"
    )

    ax.set_title(
        "Packet Delivery Ratio"
    )

    ax.grid(
        True,
        alpha=0.25
    )

    plt.tight_layout()

    if save:

        path = (
            _prepare_output()
            / "pdr_vs_round.png"
        )

        plt.savefig(
            path,
            dpi=200
        )

    if show:
        plt.show()

    else:
        plt.close(fig)

def plot_throughput(
    history,
    show=True,
    save=True
):

    if not history:
        return

    rounds = [
        row["round"]
        for row in history
    ]

    throughput = [
        row["throughput_bps"] / 1000
        for row in history
    ]

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    ax.plot(
        rounds,
        throughput
    )

    ax.set_xlabel(
        "Round"
    )

    ax.set_ylabel(
        "Throughput (kbps)"
    )

    ax.set_title(
        "Sink Throughput"
    )

    ax.grid(
        True,
        alpha=0.25
    )

    plt.tight_layout()

    if save:

        path = (
            _prepare_output()
            / "throughput_vs_round.png"
        )

        plt.savefig(
            path,
            dpi=200
        )

    if show:
        plt.show()

    else:
        plt.close(fig)