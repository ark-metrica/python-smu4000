import logging
import pathlib
import sys

# set up logging before module import to capture import module log messages
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s|%(name)s|%(levelname)s|%(message)s"
)
logger = logging.getLogger(__name__)

if "smu4000" not in sys.modules:
    # if running locally from the examples folder without having installed the library
    # add the project directory to the system path
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import smu4000

# general measurement config
REMOTE_SENSE = True  # 4-wire
PLF = 50  # Hz
NPLC = 1
SETTLING_DELAY = 0.005  # seconds

SOURCE_VOLT = "volt"
I_COMPLIANCE = 0.1  # A
SWEEP_POINTS = 51
SWEEP_SPACING = "lin"

# voltage sweep config
V_START = -1  # V
V_STOP = 1  # V


def run_sweep(host: str, port: int, timeout: float):
    """Run a source voltage sweep.

    Parameters
    ----------
    host : str
        Host name.
    port : int
        Network port.
    timeout : float
        Socket timeout in seconds.
    """
    # instantiate smu channel object in a context manager to automatically handle
    # connection and disconnection
    with smu4000.Smu4000(host, port, timeout) as smu:
        # get channel number
        channel = smu.channel

        # report channel identity
        logger.info(f"Connected to channel {channel}: {smu.idn}")

        # reset to default state
        smu.reset()

        # make sure output is disabled
        smu.output_enabled = False

        # set remote sense configuration
        smu.remote_sense = REMOTE_SENSE

        # set plf
        smu.line_frequency = PLF

        # set measurement nplc
        smu.nplc = NPLC

        # set settling delay
        smu.auto_settling_delay = False
        smu.settling_delay = SETTLING_DELAY

        # --- source voltage ---
        logger.info(f"Sourcing voltage, measuring current on channel {channel}...")

        # configure the default value of the source when the output is enabled to be
        # consistent with the measurement
        smu.configure_dc(
            source_function=SOURCE_VOLT,
            source_value=V_START,
            compliance=I_COMPLIANCE,
        )

        # configure the sweep
        smu.configure_sweep(
            source_function=SOURCE_VOLT,
            sweep_start=V_START,
            sweep_stop=V_STOP,
            sweep_points=SWEEP_POINTS,
            sweep_spacing=SWEEP_SPACING,
            compliance=I_COMPLIANCE,
        )

        # run sweep measurement
        est_sweep_time = smu.estimate_measurement_timeout()
        smu.output_enabled = True
        sweep_data = smu.measure(est_sweep_time)
        smu.output_enabled = False

        # print sweep data after output has been disabled
        logger.info(f"Channel {channel} sweep data: {sweep_data}")


if __name__ == "__main__":
    HOST = "10.1.1.165"
    PORT = 50001  # channel 1
    TIMEOUT = 3  # seconds

    run_sweep(HOST, PORT, TIMEOUT)
