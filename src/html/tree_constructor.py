"""
THIS STAGE TAKES INPUT FROM THE TOKENIZER (LIST OF TOKENS) AND WILL GENERATE AN HTML
DOCUMENT "TREE" AS THE OUTPUT.
"""


class HTMLParser:
    def __init__(self, stream):

        # SOURCE STREAM (LIST OF TOKENS)
        self.stream = stream

        # READ HEAD
        self.index = 0
        self.current_tok = {}
        self.next_tok = {}

        # STATE VARIABLES
        self.mode = "initial"
        self.reconsuming = False

    def consume(self, step):
        # UPDATE TOKENS
        if self.index < len(self.stream):
            if not self.reconsuming:
                # PUT NEXT TOKEN IN CURRENT TOKEN AND SET NEXT TOKEN AS THE ELEMENT AT THE CURRENT INDEX
                self.current_tok = self.next_tok
                self.next_tok = self.stream[self.index]
                # ONCE DONE UPDATING TOKENS MOVE AHEAD BY ONE
                self.index += step
            # RECONSUMING
            else:
                self.reconsuming = False
        else:
            if not self.reconsuming:
                self.current_tok = self.next_tok
                self.next_tok = {"token-type": "EOF-token"}
                self.index += step
            # RECONSUMING
            else:
                self.reconsuming = False
        return self.current_tok, self.next_tok

    # INSERTION MODES
    def initial(self):
        pass
