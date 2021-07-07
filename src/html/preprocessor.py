"""
THIS MODULE MANIPULATES THE INPUT STREAM WITH THE RULES DEFINED IN THE PRE PROCESSING SECTION
OF HTML SPECIFICATION.
"""


# noinspection PyMethodMayBeStatic
class PreProcessor:

    def __init__(self, stream):
        self.stream = stream

    def normalize_newlines(self, stream):
        # U+000D = CARRIAGE RETURN AND U+000A = NEWLINE OR LINEFEED
        stream = stream.replace("\u000D\u000A", "\u000A")
        stream = stream.replace("\u000D", "\u000A")
        return stream

    def process(self):
        stream = self.stream
        processed_stream = self.normalize_newlines(stream)
        return processed_stream
