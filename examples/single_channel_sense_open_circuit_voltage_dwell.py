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

SOURCE_CURR = "curr"
V_COMPLIANCE = 3  # V

# dc current config (0A at open-circuit)
I_DC = 0.0  # A

# dwell config
DWELL_TIME = 3  # seconds


def run_voc(host: str, port: int, timeout: float):
    """Run a Voc dwell measurement.

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

        # --- measure voc ---
        logger.info(f"Measuring Voc on channel {channel}...")

        # configure a dummy dc measurement to allow an accurate measurement time to be
        # estimated
        smu.configure_dc(
            source_function=SOURCE_CURR,
            source_value=I_DC,
            compliance=V_COMPLIANCE,
        )

        # run DC dwell measurement with the output disabled, i.e. with high impedance,
        # which is more accurate than actively sourcing 0A.
        est_dc_time = smu.estimate_measurement_timeout()
        dwell_data = smu.measure_until(DWELL_TIME, est_dc_time)

        # print dwell data after output has been disabled
        logger.info(f"Channel {channel} dwell data: {dwell_data}")
        logger.info(f"Channel {channel} dwell points: {len(dwell_data)}")
        logger.info(
            f"Channel {channel} dwell time: {dwell_data[-1][-2] - dwell_data[0][-2]} ms"
        )


if __name__ == "__main__":
    HOST = "10.1.1.165"
    PORT = 50001  # channel 1
    TIMEOUT = 3  # seconds

    run_voc(HOST, PORT, TIMEOUT)
