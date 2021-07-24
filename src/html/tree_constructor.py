"""
THIS STAGE TAKES INPUT FROM THE TOKENIZER (LIST OF TOKENS) AND WILL GENERATE AN HTML
DOCUMENT "TREE" AS THE OUTPUT.
"""
from src.html.dom import *


class HTMLParser:
    whitespace = ["\t", "\n", "\f", "\r", " "]

    def __init__(self, stream):

        # SOURCE STREAM (LIST OF TOKENS)
        self.stream = stream

        # READ HEAD
        self.index = 0
        self.current_tok = {}
        self.next_tok = {}

        # STATE VARIABLES
        self.mode = self.initial
        self.reconsuming = False

        # DOCUMENT
        self.document = Document()

        # STACKS
        self.stack_of_open_elem = []

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

    def insert_a_comment(self, current_token, document_obj):
        pass

    # INSERTION MODES
    def initial(self):
        pass

    def before_html(self):
        current_tok = self.current_tok
        token_type = current_tok["token-type"]

        if token_type == "DOCTYPE":
            # GENERATE PARSE ERROR
            return
        elif token_type == "comment":
            self.insert_a_comment(current_tok, self.document)
        elif token_type in self.whitespace:
            return
        elif token_type == "start-tag" and current_tok["tag-name"] == "html":
            element = self.create_element_for_token("HTML", self.document)
            self.document.add_child(element)
            self.stack_of_open_elem.append(element)
            self.mode = self.before_head
            return
        elif token_type == "end-tag" and current_tok["tag-name"] not in ["head", "body", "br", "html"]:
            # GENERATE PARSE ERROR
            return
        else:
            element = Html(node_document=self.document)
            self.document.add_child(element)
            self.stack_of_open_elem.append(element)
            self.mode = self.before_head
            return

