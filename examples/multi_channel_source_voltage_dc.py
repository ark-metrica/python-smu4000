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

# dc voltage config
V_DC = 1  # V


def run_dc(config: dict):
    """Run a source DC voltage measurement.

    Parameters
    ----------
    config : dict
        Configuration dictionary containing `host`, `port`, and `timeout` keywords
        for the Smu4000 constructor.
    """
    # instantiate smu channel object in a context manager to automatically handle
    # connection and disconnection
    with smu4000.Smu4000(**config) as smu:
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

        # setup a DC measurement
        smu.configure_dc(
            source_function=SOURCE_VOLT,
            source_value=V_DC,
            compliance=I_COMPLIANCE,
        )

        # run DC measurement
        est_dc_time = smu.estimate_measurement_timeout()
        smu.output_enabled = True
        dc_data = smu.measure(est_dc_time)
        smu.output_enabled = False

        # print DC data after output has been disabled
        logger.info(f"Channel {channel} DC data: {dc_data}")


if __name__ == "__main__":
    import multiprocessing

    HOST = "10.1.1.165"
    TIMEOUT = 3  # seconds

    # one port for each channel
    PORTS = [50001, 50002, 50003, 50004]

    # config for each channel
    CONFIGS = [{"host": HOST, "port": PORT, "timeout": TIMEOUT} for PORT in PORTS]

    # run measurement function on each channel in parallel
    with multiprocessing.Pool(len(PORTS)) as pool:
        pool.map(run_dc, CONFIGS)
