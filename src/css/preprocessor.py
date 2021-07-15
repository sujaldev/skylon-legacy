"""
THIS MODULE MANIPULATES THE INPUT STREAM WITH THE RULES DEFINED IN THE PRE PROCESSING SECTION
OF CSS SPECIFICATION.
"""


# noinspection PyMethodMayBeStatic
class PreProcessor:
    """
    NULL                     -> U+0000 -> "\0"
    LINE FEED/NEWLINE        -> U+000A -> "\n
    FORM FEED                -> U+000C -> "\f"
    CARRIAGE RETURN          -> U+000D -> "\r"
    SPACE CHARACTER          -> U+0020 -> " "
    """
    null = "\u0000"

    newline = "\u000A"
    form_feed = "\u000C"
    carriage_return = "\u000D"

    def __init__(self, stream):
        self.stream = stream

    def filter_stream(self, stream):
        """
        PROCESS OF FILTERING STREAM IS DEFINED IN THE CSS SPECIFICATION AS,
        REPLACING ALL CARRIAGE RETURN CHARACTERS, FORM FEED CHARACTERS AND
        ALL CARRIAGE RETURN AND LINE FEED CHARACTER PAIRS WITH A SINGLE
        LINE FEED CHARACTER.
        """
        stream = stream.replace(self.carriage_return + self.newline, self.newline)
        stream = stream.replace(self.carriage_return, self.newline)
        stream = stream.replace(self.form_feed, self.newline)
        return stream

    def process(self):
        stream = self.filter_stream(self.stream)
        stream = stream.replace("\0", "\uFFFD")
        return stream
