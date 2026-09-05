from pathlib import Path

import matplotlib.pyplot as plt


def plot_hop_distribution(
    routes: dict,
    show: bool = True,
    save: bool = True
):

    hop_counts = [
        route.hop_count
        for route in routes.values()
        if route is not None
    ]

    if not hop_counts:
        return

    fig, ax = plt.subplots(
        figsize=(9, 6)
    )

    minimum = min(hop_counts)
    maximum = max(hop_counts)

    bins = range(
        minimum,
        maximum + 2
    )

    ax.hist(
        hop_counts,
        bins=bins,
        align="left",
        edgecolor="black"
    )

    ax.set_xlabel(
        "Minimum Hop Count"
    )

    ax.set_ylabel(
        "Number of Sensors"
    )

    ax.set_title(
        "Minimum-Hop Distribution"
    )

    ax.grid(
        True,
        alpha=0.2
    )

    plt.tight_layout()

    if save:

        output_dir = Path(
            "outputs"
        )

        output_dir.mkdir(
            exist_ok=True
        )

        output_path = (
            output_dir
            / "minimum_hop_distribution.png"
        )

        plt.savefig(
            output_path,
            dpi=200
        )

        print(
            "Hop distribution saved to: "
            f"{output_path}"
        )

    if show:
        plt.show()

    else:
        plt.close(fig)