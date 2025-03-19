from collections import OrderedDict
import errno
import inspect
import logging
import time
import re
import select
import socket


RX_TERMCHAR = "\r"
TX_TERMCHAR = "\r"

ERR_QUERY = "syst:err:all?"
NO_ERR_MSG = "+000, No Error"
ERR_REGEX = re.compile(r"^([-+]\d{3},[^;]+)(;[-+]\d{3},[^;]+)*$")


class Smu4000:
    """Interface for controlling an Ark Metrica SMU-4000 sourcemeter channel."""

    def __init__(self, host: str, port: int, timeout: float = 3):
        """Construct object.

        Parameters
        ----------
        host : str
            Host name.
        port : int
            Network port.
        timeout : float
            Socket timeout in seconds.
        """
        # setup logging
        self.logger = logging.getLogger(__name__)

        self._host: str = host
        self._port: int = port
        self._timeout: float = timeout

        # socket for managing connection
        self._socket: None | socket.socket = None

        # hold latest error message
        self._err: str = ""

        # container for state of all smu parameters
        # DANGER! DO NOT EDIT MANUALLY!
        self.__state = OrderedDict()

        self.logger.debug("Smu4000 initialized.")

    @property
    def host(self) -> str:
        return self._host

    @host.setter
    def host(self, host: str):
        if self.connected:
            raise ValueError("Host cannot be updated whilst socket is open.")

        self._host = host

    @property
    def port(self) -> int:
        return self._port

    @port.setter
    def port(self, port: int):
        if self.connected:
            raise ValueError("Port cannot be updated whilst socket is open.")

        self._port = port

    @property
    def timeout(self) -> float:
        if self._socket:
            timeout = self._socket.gettimeout()

            if timeout:
                return timeout
            else:
                raise ValueError("Socket timeout not initialised.")
        else:
            return self._timeout

    @timeout.setter
    def timeout(self, timeout: float):
        if self._socket:
            self._socket.settimeout(timeout)

        self._timeout = timeout

    @property
    def channel(self) -> int:
        return self._port - 50000

    @property
    def idn(self) -> str:
        """Identity string"""
        if self.connected:
            return self.query("*IDN?")
        else:
            return ""

    @property
    def idn_dict(self) -> dict:
        """Decomposed identity string into dictionary"""
        _dict = {
            "manufacturer": "",
            "model": "",
            "ctrl_serial": "",
            "ctrl_firmware": "",
            "ch_serial": "",
            "ch_firmware": "ch_firmware",
        }

        if self.connected:
            manufacturer, model, ctrl_serial, ctrl_firmware, ch_serial, ch_firmware = (
                self.idn.split(",")
            )

            _dict["manufacturer"] = manufacturer
            _dict["model"] = model
            _dict["ctrl_serial"] = ctrl_serial
            _dict["ctrl_firmware"] = ctrl_firmware
            _dict["ch_serial"] = ch_serial
            _dict["ch_firmware"] = ch_firmware

        return _dict

    @property
    def line_frequency(self) -> int:
        return int(self.query("syst:lfr?"))

    @line_frequency.setter
    def line_frequency(self, frequency: int):
        if frequency not in [50, 60]:
            raise ValueError(
                f"Invalid line frequency: {frequency}. Must be '50' or '60'."
            )

        self.write(f"syst:lfr {frequency}")

    @property
    def connected(self) -> bool:
        if self._socket:
            return True
        else:
            return False

    @property
    def status_byte(self) -> int:
        return int(self.query("*STB?"))

    @property
    def source_function(self) -> str:
        return self.query("sour:func?")

    @source_function.setter
    def source_function(self, function: str):
        if function not in ["volt", "curr"]:
            raise ValueError(
                r"Invalid source function. Source function must be either 'curr' or 'volt'."
            )
        self.write(f"sour:func {function}")

        self.__update_state()

    @property
    def output_enabled(self) -> bool:
        return bool(int(self.query("outp?")))

    @output_enabled.setter
    def output_enabled(self, enabled: bool):
        if enabled:
            self.write("outp 1")
        else:
            self.write("outp 0")

        self.__update_state()

    @property
    def nplc(self) -> float:
        return float(self.query("sens:curr:nplc?"))

    @nplc.setter
    def nplc(self, nplc: float):
        self.write(f"sens:curr:nplc {nplc:0.6f}")

        # for compatibility with central control
        self.nplc_user_set = nplc

        self.__update_state()

    @property
    def settling_delay(self) -> float:
        """Settling delay in s."""
        return float(self.query("sour:del?"))

    @settling_delay.setter
    def settling_delay(self, delay: float):
        """Settling delay in s."""
        self.write(f"sour:del {delay:0.6f}")

        self.__update_state()

    @property
    def auto_settling_delay(self) -> bool:
        return bool(int(self.query("sour:del:auto?")))

    @auto_settling_delay.setter
    def auto_settling_delay(self, auto: bool):
        if auto:
            self.write("sour:del:auto 1")
        else:
            self.write("sour:del:auto 0")

        self.__update_state()

    @property
    def source_voltage(self) -> float:
        return float(self.query("sour:volt?"))

    @source_voltage.setter
    def source_voltage(self, voltage: float):
        self.write(f"sour:volt {voltage:0.6f}")

        self.__update_state()

    @property
    def source_current(self) -> float:
        return float(self.query("sour:curr?"))

    @source_current.setter
    def source_current(self, current: float):
        self.write(f"sour:curr {current:0.6f}")

        self.__update_state()

    @property
    def compliance_voltage(self) -> float:
        return float(self.query("sens:volt:prot?"))

    @compliance_voltage.setter
    def compliance_voltage(self, voltage: float):
        self.write(f"sens:volt:prot {voltage:0.6f}")

        self.__update_state()

    @property
    def compliance_current(self) -> float:
        return float(self.query("sens:curr:prot?"))

    @compliance_current.setter
    def compliance_current(self, current: float):
        self.write(f"sens:curr:prot {current:0.6f}")

        self.__update_state()

    @property
    def sweep_start_voltage(self) -> float:
        return float(self.query("sour:volt:start?"))

    @sweep_start_voltage.setter
    def sweep_start_voltage(self, voltage: float):
        self.write(f"sour:volt:start {voltage:0.6f}")

        self.__update_state()

    @property
    def sweep_start_current(self) -> float:
        return float(self.query("sour:curr:start?"))

    @sweep_start_current.setter
    def sweep_start_current(self, current: float):
        self.write(f"sour:curr:start {current:0.6f}")

        self.__update_state()

    @property
    def sweep_stop_voltage(self) -> float:
        return float(self.query("sour:volt:stop?"))

    @sweep_stop_voltage.setter
    def sweep_stop_voltage(self, voltage: float):
        self.write(f"sour:volt:stop {voltage:0.6f}")

        self.__update_state()

    @property
    def sweep_stop_current(self) -> float:
        return float(self.query("sour:curr:stop?"))

    @sweep_stop_current.setter
    def sweep_stop_current(self, current: float):
        self.write(f"sour:curr:stop {current:0.6f}")

        self.__update_state()

    @property
    def sweep_points(self) -> int:
        return int(self.query("sour:swe:poin?"))

    @sweep_points.setter
    def sweep_points(self, points: int):
        self.write(f"sour:swe:poin {points}")

        self.__update_state()

    @property
    def sweep_spacing(self) -> str:
        return self.query("sour:swe:spac?")

    @sweep_spacing.setter
    def sweep_spacing(self, spacing: str):
        if spacing not in ["lin", "log"]:
            raise ValueError(
                r"Invalid sweep spacing. Sweep spacing must be either 'lin' or 'log'."
            )
        self.write(f"sour:swe:spac {spacing}")

        self.__update_state()

    @property
    def source_voltage_mode(self) -> str:
        return self.query("sour:volt:mode?")

    @source_voltage_mode.setter
    def source_voltage_mode(self, mode: str):
        if mode not in ["fix", "swe", "list"]:
            raise ValueError(
                r"Invalid source mode. Source mode must be either 'fix', 'swe', or 'list'."
            )
        self.write(f"sour:volt:mode {mode}")

        self.__update_state()

    @property
    def source_current_mode(self) -> str:
        return self.query("sour:curr:mode?")

    @source_current_mode.setter
    def source_current_mode(self, mode: str):
        if mode not in ["fix", "swe", "list"]:
            raise ValueError(
                r"Invalid source mode. Source mode must be either 'fix', 'swe', or 'list'."
            )
        self.write(f"sour:curr:mode {mode}")

        self.__update_state()

    @property
    def remote_sense(self) -> bool:
        if self.connected:
            return bool(int(self.query("syst:rsen?")))
        else:
            # for compatibility with central control
            return not self._two_wire

    @remote_sense.setter
    def remote_sense(self, remote_sense: bool):
        if remote_sense:
            self.write("syst:rsen 1")
        else:
            self.write("syst:rsen 0")

        # for compatibility with central control
        self._two_wire = not remote_sense

        self.__update_state()

    def __enter__(self):
        """Enter a context."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Leave context cleanly."""
        # turn off output
        self.output_enabled = False

        # close connection
        self.disconnect()

    def connect(self):
        """Open a connection to the instrument."""
        if self.connected:
            self.disconnect()
            time.sleep(1)

        remaining_connection_retries = 5
        while remaining_connection_retries > 0:
            try:
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.connect((self._host, self._port))
                self._socket.settimeout(self._timeout)
                break
            except ConnectionRefusedError:
                self.logger.debug("Connection attempt refused")

                # Close the previous connection attempt
                if self._socket:
                    self.disconnect()

                # controller may need longer to re-open socket after it was last closed
                # wait and try again
                time.sleep(1)

            remaining_connection_retries -= 1
            self.logger.debug(
                "Connection retries remaining: %d", remaining_connection_retries
            )
        else:
            raise ConnectionError(
                f"Connection retries exhausted while connecting to {self.host}:{self.port}"
            )

        # make sure socket buffer is clean
        self._clear_buffer()

        self.logger.debug("SMU-4000 connected!")

    def disconnect(self):
        """Close the connection to the instrument."""
        if self._socket:
            try:
                # shut down both send and receive
                self._socket.shutdown(socket.SHUT_RDWR)
            except (socket.error, OSError):
                # ignore errors if already closed
                pass
            finally:
                # ensure the socket is closed
                self._socket.close()

                # remove reference to free memory
                self._socket = None

    def read(self) -> str:
        if not self._socket:
            raise ValueError("SMU communications not initialised.")

        RX_TERMCHAR_BYTE = RX_TERMCHAR.encode()
        data = bytearray()

        # try to read one byte at a time until termchar is reached
        try:
            while True:
                byte = self._socket.recv(1)

                if byte == b"":
                    self.logger.error("Connection closed by peer")
                    break

                data.extend(byte)

                if byte == RX_TERMCHAR_BYTE:
                    # terminator is found so stop
                    break
        except socket.timeout:
            self.logger.error("Socket read timed out")
        except socket.error as e:
            self.logger.error(f"Socket error: {e}")

        # decode and return response
        return bytes(data).decode().removesuffix(RX_TERMCHAR)

    def write(self, cmd: str):
        if not self._socket:
            raise ValueError("SMU communications not initialised")

        cmd_bytes = len(cmd)

        write_retries = 3
        while write_retries > 0:
            try:
                bytes_written = self._socket.send((cmd + TX_TERMCHAR).encode())
                if cmd_bytes != (bytes_written - len(TX_TERMCHAR)):
                    raise ValueError(
                        f"Write failure, {bytes_written - len(TX_TERMCHAR)} != {cmd_bytes}."
                    )
                break
            except socket.error as e:
                if e.errno == errno.ECONNRESET:
                    self.logger.error("Connection reset by peer on write.")
                else:
                    self.logger.error(
                        f"Socket error occurred on write: [{e.errno}] "
                        + f"{errno.errorcode.get(e.errno or 0, 'UNKNOWN_ERROR')} ({e})."
                    )
            except ValueError:
                # re-raise commands bytes error
                raise
            except Exception as e:
                self.logger.error("Error occurred on write: %s.", str(e))

            # any error that gets this far should be resolved by reconnecting and
            # retrying
            self.connect()

            write_retries -= 1
        else:
            raise IOError("Write operation exceeded maximum retries.")

        if not cmd.endswith("?"):
            # write wasn't a query so check for write errors
            # this also limits the message rate so the controller buffer isn't exceeded
            self.query_error()

    def query(self, question: str) -> str:
        """Write a question and read the response.

        Parameters
        ----------
        question : str
            Question to ask the device.

        Returns
        -------
        response : str
            Response to the question.
        """
        query_retries = 3
        while query_retries > 0:
            self.write(question)

            try:
                response = self.read()

                if response != "":
                    break
                else:
                    raise ValueError("Read returned an empty string")
            except (socket.timeout, ValueError) as e:
                self.logger.error(f"{e}")

                # check if timeout occurred because request command was invalid (in
                # which case, stop and raise the error) or if it was a comms timeout
                # (in which case, try dummy query to force read).
                # the error query is never invalid so just reconnect and retry.
                if question != ERR_QUERY:
                    try:
                        self.write(ERR_QUERY)
                        err = self.read()

                        if err != "" and not ERR_REGEX.match(err):
                            # response to error query wasn't an error message so was
                            # probably the stuck previous message
                            response = err

                            # input buffer now has the dummy error response so clear it
                            dummy_err = self.read()
                            self.logger.debug(f"Dummy error contents: {dummy_err}")

                            # give controller a bit more time to send anything else
                            # and try to clear the buffer
                            time.sleep(0.5)
                            self._clear_buffer()

                            break
                        elif err != NO_ERR_MSG and ERR_REGEX.match(err):
                            # received real error msg so question was probably invalid
                            raise ValueError(err)
                        else:
                            self.logger.debug(
                                f"Read timeout validation returned unexpected str: {err}"
                            )
                    except Exception as e:
                        self.logger.error(
                            f"Error occurred during read timeout validation: {e}."
                        )
            except socket.error as e:
                if e.errno == errno.ECONNRESET:
                    self.logger.error("Connection reset by peer on read.")
                else:
                    self.logger.error(
                        f"Socket error occurred on read: [{e.errno}] "
                        + f"{errno.errorcode.get(e.errno or 0, 'UNKNOWN_ERROR')} ({str(e)})."
                    )
            except Exception as e:
                self.logger.error(f"Error occurred on read: {e}.")

            # any error that gets this far should be resolved by reconnecting and
            # retrying
            self.connect()

            query_retries -= 1
        else:
            raise IOError(f"Query exceeded maximum retries: '{question}'.")

        return response

    def query_error(self, ignore: bool = False):
        """Read the SMU error buffer.

        Parameters
        ----------
        ignore : bool
            If True, ignore the error returned to clear the buffer. If False, raise
            the error.
        """
        self._err = self.query(ERR_QUERY)

        if self._err != NO_ERR_MSG and not ignore and ERR_REGEX.match(self._err):
            # valid error message, not ignoring it, but showing an error
            raise ValueError(self._err)
        elif not ERR_REGEX.match(self._err):
            self.logger.debug(f"invalid error message: {self._err}")
            raise ValueError(self._err)

    def reset(self, hard: bool = False):
        """Reset SMU channel.

        Parameters
        ----------
        hard : bool
            If `False`, perform a software reset. If `True`, force the SMU PCB to power
            cycle. The power cycle requires a ~5s delay before the SMU channel can
            respond to commands again.
        """
        if hard:
            self.write("*RST")
            time.sleep(6)  # wait for smu channel to reset
        else:
            self.write("syst:pres")

        # clear error buffer
        self.query_error(ignore=True)

        # reset state
        self.__state = OrderedDict()

    def configure_dc(
        self, source_function: str, source_value: float, compliance: float
    ):
        """Configure the DC output.

        Parameters
        ----------
        source_function : str
            The source mode for the output: "volt" or "curr".
        source_value : float
            Output value for source function.
        compliance : float
            Compliance value for sense function.
        """
        if source_function == "volt":
            self.compliance_current = abs(compliance)
            self.source_function = source_function
            self.source_voltage_mode = "fix"
            self.source_voltage = source_value
        elif source_function == "curr":
            self.compliance_voltage = abs(compliance)
            self.source_function = source_function
            self.source_current_mode = "fix"
            self.source_current = source_value
        else:
            raise ValueError(
                f"Invalid source function: {source_function}. Must be 'volt' or 'curr'."
            )

    def configure_sweep(
        self,
        source_function: str,
        sweep_start: float,
        sweep_stop: float,
        sweep_points: int,
        sweep_spacing: str,
        compliance: float,
    ):
        """Configure a source sweep.

        Parameters
        ----------
        source_function : str
            The source mode for the output: "volt" or "curr".
        sweep_start : float
            Output value for source function at sweep start.
        sweep_stop : float
            Output value for source function at sweep stop.
        sweep_points : int
            Number of points in the sweep.
        sweep_spacing : str
            Point spacing in sweep: "lin" (linear) or "log" (logarithmic).
        compliance : float
            Compliance value for sense function.
        """
        if source_function == "volt":
            self.source_function = source_function
            self.compliance_current = abs(compliance)
            self.sweep_start_voltage = sweep_start
            self.sweep_stop_voltage = sweep_stop
            self.source_voltage_mode = "swe"
        elif source_function == "curr":
            self.source_function = source_function
            self.compliance_voltage = abs(compliance)
            self.sweep_start_current = sweep_start
            self.sweep_stop_current = sweep_stop
            self.source_current_mode = "swe"
        else:
            raise ValueError(
                f"Invalid source function: {source_function}. Must be 'volt' or 'curr'."
            )

        self.sweep_spacing = sweep_spacing
        self.sweep_points = sweep_points

    def measure(
        self, timeout: float | None = None
    ) -> list[tuple[float, float, float, int]]:
        """Make a measurement and return the result.

        Parameters
        ----------
        timeout : float | None
            Maximum period to wait for read to return data in seconds. Reads can take a
            long time depending on the measurement configuration (source_delay, nplc,
            sweep_points) so the default timeout may be exceeded. Change the timeout
            based on the measurement configuration to avoid read timeout errors. If
            `None`, use the current timeout setting. This timeout setting only applies
            to this read event and the previous timeout setting is restored after data
            has been acquired.

        Returns
        -------
        data : list[tuple[float, float, float, int]]
            Measurement data formatted as a list of tuples of values. The length of the
            list depends on the source configuration. If the source is configured to
            sweep, the list will have a length of `sweep_points`.
        """
        if self._socket:
            # set timeout
            old_timeout = self._socket.gettimeout()
            if timeout:
                self._socket.settimeout(timeout)

            # if wdt has occurred since last check, restore state
            self._check_wdt_reset_bit(restore_state=True)

            data = []
            raw_data = self.query("read?")
            raw_data_list = raw_data.split(",")
            for i in range(0, len(raw_data_list), 4):
                line = (
                    float(raw_data_list[i]),
                    float(raw_data_list[i + 1]),
                    float(raw_data_list[i + 2]),
                    int(raw_data_list[i + 3]),
                )
                data.append(line)

            # restore timeout
            if timeout:
                self._socket.settimeout(old_timeout)
        else:
            raise ConnectionError("Not connected.")

        return data

    def measure_until(
        self, t_dwell: float, timeout: float | None = None
    ) -> list[tuple[float, float, float, int]]:
        """Makes a series of single DC measurements.

        The source must already be configured in 'fix' mode otherwise this function
        will raise an error.

        Parameters
        ----------
        t_dwell : float
            Period over which to repeat single measurements as fast as possible, in
            seconds.
        timeout : float | None
            Maximum period to wait for each single read to return data in seconds.
            Reads can take a long time depending on the measurement configuration
            (source_delay, nplc, sweep_points) so the default timeout may be exceeded.
            Change the timeout based on the measurement configuration to avoid read
            timeout errors. If `None`, use the current timeout setting. This timeout
            setting only applies to each read event and the previous timeout setting
            is restored after data has been acquired.

        Returns
        -------
        data : list[tuple[float, float, float, int]]
            Measurement data formatted as a list of tuples of values. The length of the
            list depends on the source configuration. If the source is configured to
            sweep, the list will have a length of `sweep_points`.
        """
        # check if source is configured for dc measurements
        invalid = False
        if self.source_function == "volt":
            if self.source_voltage_mode != "fix":
                invalid = True
        else:
            if self.source_current_mode != "fix":
                invalid = True

        if invalid:
            raise ValueError(
                "Invalid source mode for `measure_until`. Source mode must be 'fix'."
            )

        data = []
        t_end = time.time() + t_dwell
        while time.time() < t_end:
            datum = self.measure(timeout)
            data.extend(datum)

        return data

    def estimate_measurement_timeout(self, scale: float = 1.2) -> float:
        """Query measurement configuration to estimate timeout for the `read` function.

        The timeout is calculated as the scaled measurement time plus the socket
        timeout.

        Parameters
        ----------
        scale : float
            Scaling factor to account for additional measurement overhead time. Must
            be >= 1.

        Returns
        -------
        timeout : float
            Timeout in seconds.
        """
        if scale < 1:
            raise ValueError("Scale must be greater than or equal to 1.")

        if self.auto_settling_delay:
            delay = 1e-3
        else:
            delay = self.settling_delay

        measurement_time_per_point = delay + self.nplc / self.line_frequency

        if self.source_function == "volt":
            if self.source_voltage_mode == "swe":
                points = self.sweep_points
            else:
                points = 1
        else:
            if self.source_current_mode == "swe":
                points = self.sweep_points
            else:
                points = 1

        return scale * points * measurement_time_per_point + self.timeout

    def _clear_buffer(self):
        """Clear the socket receive buffer."""
        if self._socket:
            buffer = bytearray()

            try:
                while True:
                    # check if data is available to read (non-blocking)
                    readable, _, _ = select.select([self._socket], [], [], 0)
                    if not readable:
                        # no data left in buffer, exit loop
                        break

                    # read one byte of buffer contents
                    buffer.extend(self._socket.recv(1))

                if len(buffer) > 0:
                    self.logger.debug(
                        f"Cleared buffer contents: {bytes(buffer).decode()}"
                    )
            except socket.timeout:
                pass
        else:
            raise ConnectionError("Socket is not connected so cannot clear buffer.")

    def __update_state(self):
        """Add a method and its arguments to the _state dictionary for recall later.

        This method should be called at the end of every property setter method that
        relates to the SMU state, e.g. set voltage, source function etc. It stores the
        property name and the property's arguments as a key, value pair in the _state
        dictionary. The dictionary can later be called to replay the setter calls and
        recover the last known state in the unlikely event of a watchdog timeout of
        the SMU channel.

        This method should never be called outside of the class. The double underscore
        invokes name mangling to make this difficult.
        """
        # Get the calling frame
        frame = inspect.currentframe()

        frame_info_missing = False
        if frame:
            caller_frame = frame.f_back

            if caller_frame:
                # Get the method object and its signature
                method_name = caller_frame.f_code.co_name

                # Attempt to retrieve the attribute
                attr = getattr(self.__class__, method_name, None)

                # Check if the attribute is a property or a method
                if isinstance(attr, property):
                    # It's a property; use the setter for the signature
                    method = attr.fset  # fset is the setter method of the property
                elif callable(attr):
                    # It's a regular method
                    method = attr
                else:
                    raise TypeError(
                        f"{method_name!r} is neither a property nor a method."
                    )

                if method:
                    sig = inspect.signature(method)

                    # Get local variables
                    local_vars = dict(caller_frame.f_locals)

                    # Bind the arguments to the method's signature, excluding local variables not
                    # in the method's signature
                    bound_args = sig.bind_partial(**local_vars)

                    # If the method is already in the ordered state dictionary, remove it reinsert
                    # so it can be reinserted at the end
                    if method in self.__state:
                        del self.__state[method]

                    # Store the callable in the _state dictionary as the method and its bound
                    # arguments
                    self.__state[method] = bound_args
                else:
                    frame_info_missing = True
            else:
                frame_info_missing = True
        else:
            frame_info_missing = True

        if frame_info_missing:
            self.logger.warning("`frame` is `None` - cannot update state.")

    def _restore_state(self):
        """Restore the SMU state using the _state dictionary.

        This should only be called to restore state in the unlikely event of an SMU
        watchdog timeout.
        """
        # iterate over a copy to avoid issues caused by mutating self.__state when
        # methods get called that modify self.__state
        state_items = list(self.__state.items())
        for method, bound_args in state_items:
            method(*bound_args.args, **bound_args.kwargs)
            self.logger.debug(
                f"Restored: {method}, {bound_args.args}, {bound_args.kwargs}"
            )

    def _check_wdt_reset_bit(self, restore_state: bool = False):
        """Check if WDT bit of status byte is set.

        Optionally, restore the saved state if it is.

        Parameters
        ----------
        restore_state : bool
            If `True`, restore saved state if WDT bit is set.
        """
        wdt_bit_set = self.status_byte & (1 << 0) != 0

        if wdt_bit_set:
            self.logger.warning("WDT bit set")
            self._clear_wdt_bit()

            if restore_state:
                self._restore_state()
                self.logger.warning("State restored")

    def _clear_wdt_bit(self):
        self.write("syst:wdt:cle")
