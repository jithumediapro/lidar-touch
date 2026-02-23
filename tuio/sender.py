from pythonosc.osc_bundle_builder import OscBundleBuilder, IMMEDIATELY
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.udp_client import SimpleUDPClient


class TuioSender:
    """TUIO 1.1 /tuio/2Dcur sender over UDP."""

    SOURCE_NAME = "HokuyoTouch"

    def __init__(self, host="127.0.0.1", port=3333):
        self._client = SimpleUDPClient(host, port)
        self._enabled = True

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, value):
        self._enabled = value

    def update_target(self, host, port):
        self._client = SimpleUDPClient(host, port)

    def send_frame(self, touches, frame_seq):
        """Build and send a TUIO 1.1 /tuio/2Dcur bundle."""
        if not self._enabled:
            return

        try:
            bundle = OscBundleBuilder(IMMEDIATELY)

            # Source message
            source_msg = OscMessageBuilder(address="/tuio/2Dcur")
            source_msg.add_arg("source")
            source_msg.add_arg(self.SOURCE_NAME)
            bundle.add_content(source_msg.build())

            # Alive message
            alive_msg = OscMessageBuilder(address="/tuio/2Dcur")
            alive_msg.add_arg("alive")
            for touch in touches:
                alive_msg.add_arg(touch.session_id)
            bundle.add_content(alive_msg.build())

            # Set messages (one per touch)
            for touch in touches:
                set_msg = OscMessageBuilder(address="/tuio/2Dcur")
                set_msg.add_arg("set")
                set_msg.add_arg(touch.session_id)
                set_msg.add_arg(float(touch.normalized_pos[0]))
                set_msg.add_arg(float(touch.normalized_pos[1]))
                set_msg.add_arg(float(touch.velocity_xy[0]))
                set_msg.add_arg(float(touch.velocity_xy[1]))
                set_msg.add_arg(0.0)  # motion acceleration
                bundle.add_content(set_msg.build())

            # Fseq message
            fseq_msg = OscMessageBuilder(address="/tuio/2Dcur")
            fseq_msg.add_arg("fseq")
            fseq_msg.add_arg(frame_seq)
            bundle.add_content(fseq_msg.build())

            self._client.send(bundle.build())
        except Exception:
            pass  # UDP send failure is non-fatal
