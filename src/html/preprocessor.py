"""
THIS MODULE MANIPULATES THE INPUT STREAM WITH THE RULES DEFINED IN THE PRE PROCESSING SECTION
OF HTML SPECIFICATION.
"""
from lib.debugger import Debugger


# noinspection PyMethodMayBeStatic
class PreProcessor:
    """
    NULL                     -> U+0000 -> "\0"
    TAB                      -> U+0009 -> "\t"
    LINE FEED/NEWLINE        -> U+000A -> "\n"
    FORM FEED                -> U+000C -> "\f"
    CARRIAGE RETURN          -> U+000D -> "\r"
    SPACE CHARACTER          -> U+0020 -> " "
    """
    null = "\u0000"

    tab = "\u0009"
    newline = "\u000A"
    form_feed = "\u000C"
    carriage_return = "\u000D"
    space = "\u0020"

    whitespace = (tab, newline, form_feed, carriage_return, space)

    # C0 CONTROL [ALL CHARACTERS IN THE RANGE U+0000 AND U+001F (31 IN BASE 10), INCLUSIVE]
    c0_control = [chr(i) for i in range(1, 32)]

    # CONTROL CHARACTERS [ALL CHARACTERS IN THE RANGE U+007F (127 IN BASE 10) AND U+009F (159 IN BASE 10), INCLUSIVE]
    # PLUS C0 CONTROL CHARACTERS
    control_characters = c0_control + [chr(i) for i in range(127, 160)]

    # NON CHARACTER'S DEFINITION CAN BE FOUND HERE https://infra.spec.whatwg.org/#noncharacter
    non_characters = [chr(i) for i in range(64976, 65008)]
    for i in range(65534, 1114111, 65536):
        non_characters.append(chr(i))
        non_characters.append(chr(i + 1))

    def __init__(self, stream, debug_lvl=0, save_debugging_lvl=0, save_debug=False):
        self.stream = stream
        self.parse_errors = []

        # DEBUGGER
        self.debug_lvl = debug_lvl
        self.save_debugging_lvl = save_debugging_lvl
        self.save_debug = save_debug
        self.debugger = Debugger(self.debug_lvl, self.save_debugging_lvl, self.save_debug)
        self.dprint = self.debugger.print

    def generate_parse_error(self, error):
        self.parse_errors.append(error.lower().replace(" ", "-"))
        self.dprint(f"[PARSE ERROR]: [{error}]", debugging_mode=2, color="yellow")

    def normalize_newlines(self, stream):
        """
        NORMALIZING NEWLINES IS THE PROCESS OF CONVERTING ALL CARRIAGE RETURN (CR) AND NEWLINE PAIRS WITH A NEWLINE.
        THEN REPLACING ALL STANDALONE CARRIAGE RETURNS WITH A NEWLINE.
        THIS STEP ENSURES NO CARRIAGE RETURN EVER REACHES THE TOKENIZATION STAGE.
        """
        stream = stream.replace(self.carriage_return + self.newline, self.newline)
        stream = stream.replace(self.carriage_return, self.newline)
        return stream

    def handle_non_char(self,  stream):
        """
        NON CHARACTERS ARE CHARACTERS WITH CODEPOINTS IN THE RANGE U+FFD0 (64976 IN BASE 10)
        AND U+FDEF (65007 IN BASE 10), INCLUSIVE. PLUS EVERY LAST TWO CHARACTER IN EACH CODE
        PLANE.

        THESE CHARACTERS ARE TO BE PARSED "AS IS" BUT A non-character-in-input-stream parse-error
        SHOULD BE GENERATED.
        """
        for char in stream:
            if char in self.non_characters:
                self.generate_parse_error("NONCHARACTER IN INPUT STREAM")

    def handle_control_chars(self, stream):
        """
        ACCORDING TO HTML SPECIFICATION, A CONTROL CHARACTER IS A CHARACTER WITH IT'S CODEPOINT
        IN THE RANGE U+0000 (0 IN BASE 10) AND U+001F (31 IN BASE 10) INCLUSIVE OR
        IN THE RANGE U+007F (127 IN BASE 10) AND U+009F (159 IN BASE 10) INCLUSIVE.

        THESE CHARACTERS ARE TO BE PARSED "AS IS" BUT A control-character-in-input-stream parse-error
        SHOULD BE GENERATED EXCEPT WHEN CONTROL IS EITHER WHITESPACE OR NULL.
        """
        for char in stream:
            if char in self.control_characters and char not in self.whitespace and char != self.null:
                self.generate_parse_error("CONTROL CHARACTER IN INPUT STREAM")

    def process(self):
        stream = self.stream
        processed_stream = self.normalize_newlines(stream)
        self.handle_control_chars(processed_stream)
        self.handle_non_char(processed_stream)
        return processed_stream
