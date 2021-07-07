"""
THIS MODULE MANIPULATES THE INPUT STREAM WITH THE RULES DEFINED IN THE PRE PROCESSING SECTION
OF HTML SPECIFICATION.
"""


# noinspection PyMethodMayBeStatic
class PreProcessor:
    non_characters = [
        "\uFFFE", "\uFFFF", "\u1FFFE", "\u1FFFF",
        "\u2FFFE", "\u2FFFF", "\u3FFFE", "\u3FFFF",
        "\u4FFFE", "\u4FFFF", "\u5FFFE", "\u5FFFF",
        "\u6FFFE", "\u6FFFF", "\u7FFFE", "\u7FFFF",
        "\u8FFFE", "\u8FFFF", "\u9FFFE", "\u9FFFF",
        "\uAFFFE", "\uAFFFF", "\uBFFFE", "\uBFFFF",
        "\uCFFFE", "\uCFFFF", "\uDFFFE", "\uDFFFF",
        "\uEFFFE", "\uEFFFF", "\uFFFFE", "\uFFFFF",
        "\u10FFFE", "\u10FFFF"
    ]

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


if __name__  == "__main__":
    print(PreProcessor("").non_characters)