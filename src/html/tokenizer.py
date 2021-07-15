"""
THE TOKENIZER IS SUPPOSED TO CONVERT A STREAM OF HTML INTO A LIST OF HTML TOKENS.

SINCE HTML PARSERS ARE BUILT TO FORGIVE ALL SORTS OF ERRORS, HTML'S GRAMMAR CANNOT
BE DEFINED WITH REGULAR EXPRESSIONS. TO PARSE HTML ONE CAN PICTURE A STATE MACHINE
READING A STREAM OF HTML CHARACTER BY CHARACTER (POSSIBLY MORE IN SOME STATES)
WHERE EACH CHARACTER CAN BE THOUGHT OF AS AN EVENT WHICH CAN CAUSE A TRANSITION TO
ANOTHER STATE WHERE EACH STATE CAN HAVE EFFECTS LIKE TRANSITIONING TO ANOTHER STATE,
EMITTING AN HTML TOKEN, ETC.
"""
from src.html.preprocessor import HTMLPreProcessor
from lib.debugger import Debugger
import json

AMPERSAND_ENTITIES_PATH = f"{'/'.join(__file__.split('/')[:-1])}/ampersand-entities.json"
SPECIAL_NUMERIC_ENTITIES_PATH = f"{'/'.join(__file__.split('/')[:-1])}/special-numeric-entities.json"


# HELPER FUNCTIONS
def inside(iterable, char):
    if char in iterable and char != "":
        return True
    return False


class HTMLTokenizer:
    # CONSTANTS DEFINED IN THE SPECIFICATIONS
    ascii_digit = "0123456789"
    ascii_upper_hex_digit = ascii_digit + "ABCDEF"
    ascii_lower_hex_digit = ascii_digit + "abcdef"
    ascii_hex_digit = ascii_upper_hex_digit + ascii_lower_hex_digit
    ascii_upper_alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ascii_lower_alpha = "abcdefghijklmnopqrstuvwxyz"
    ascii_alpha = ascii_lower_alpha + ascii_upper_alpha
    ascii_alphanumeric = ascii_alpha + ascii_digit

    ###############################################################################################
    # INFRA STANDARD ##############################################################################
    tab = "0x0009"
    newline = "0x000A"
    form_feed = "0x000C"
    carriage_return = "0x000D"
    space = "0x0020"

    whitespace = (tab, newline, form_feed, carriage_return, space)

    # C0 CONTROL [ALL CHARACTERS IN THE RANGE U+0000 AND U+001F (31 IN BASE 10), INCLUSIVE]
    c0_control = [chr(i) for i in range(1, 32)]

    # CONTROL CHARACTERS [ALL CHARACTERS IN THE RANGE U+007F (127 IN BASE 10) AND U+009F (159 IN BASE 10), INCLUSIVE]
    # PLUS C0 CONTROL CHARACTERS
    control_characters = c0_control + [chr(i) for i in range(127, 160)]

    non_characters = [chr(i) for i in range(64976, 65008)]
    for i in range(65534, 1114111, 65536):
        non_characters.append(chr(i))
        non_characters.append(chr(i + 1))
    ###############################################################################################

    # NAMED CHARACTER REFERENCE TABLE
    with open(AMPERSAND_ENTITIES_PATH, "r") as table:
        ampersand_table = json.load(table)

    # SPECIAL NUMERIC ENTITIES REFERENCE TABLE
    with open(SPECIAL_NUMERIC_ENTITIES_PATH, "r") as table:
        special_numeric_entities_table = json.load(table)

    ###############################################################################################
    def __init__(self, stream, debug_lvl=0, save_debugging_lvl=0, save_debug=False):
        """
        The Tokenizer class tries to mimic a state machine which takes in a stream of characters
        and emits html tokens. It begins in the data state with its read head at index 0.

        :param stream: HTML string that needs to be tokenized
        """

        # INPUT
        self.stream = stream
        self.preprocessor = HTMLPreProcessor(self.stream)
        self.stream = self.preprocessor.process()  # PREPROCESSING

        # OUTPUTS
        self.output = []
        self.parse_errors = []
        self.parse_errors += self.preprocessor.parse_errors

        # STATE MACHINE'S CURRENT STATE
        self.state = self.data_state

        # STATE MACHINE FLAGS
        self.reconsuming = False
        self.out_of_index = False

        # READ HEAD
        try:
            self.index = 0
            self.next_char = self.stream[0]  # The first character in the stream to have not yet been consumed
            self.current_char = ""  # Defined as the last character to have been consumed
            self.empty_stream = False
        except IndexError:
            self.empty_stream = True

        # BUFFERS
        self.temp_buffer = ""
        self.return_state = None  # Used by char_ref_state as a buffer to return to the state it was invoked from
        self.token_buffer = {}  # Used as a temporary buffer while creating tokens
        self.char_ref_code_buffer: int = 0

        # DEBUGGER
        self.debug_lvl = debug_lvl
        self.save_debugging_lvl = save_debugging_lvl
        self.save_debug = save_debug
        self.debugger = Debugger(self.debug_lvl, self.save_debugging_lvl, self.save_debug)
        self.dprint = self.debugger.print

        # INITIATE TOKENIZING PROCESS
        self.tokenize()

    ###############################################################################################
    # OPERATIONS #
    def consume(self):
        # DEBUGGING
        mode = '[\033[34mRECONSUMING\033[0m] -> ' if self.reconsuming else '[CONSUMING]   -> '
        self.dprint(f"\n|=>{mode}", end="")

        if self.index < len(self.stream):
            if not self.reconsuming:
                self.next_char = self.stream[self.index]
                if self.index == 0:
                    self.current_char = ""
                else:
                    self.current_char = self.stream[self.index - 1]
                self.index += 1
                # DEBUGGING
                self.dprint(f"[Current Character: '{self.current_char}'] AND [Next Character: '{self.next_char}']\n")
                return self.current_char, self.next_char
            else:
                self.reconsuming = False
                # DEBUGGING
                self.dprint(f"[Current Character: '{self.current_char}'] AND [Next Character: '{self.next_char}']\n")
                return self.current_char, self.next_char
        elif self.reconsuming:
            self.reconsuming = False
            self.dprint(f"[Current Character: '{self.current_char}'] AND [Next Character: '{self.next_char}']\n")
            return self.current_char, self.next_char
        else:
            # DEBUGGING
            self.dprint(f"[Current Character: '{self.stream[-1]}' | Next Character: '']")
            self.dprint("|=>[OUT OF INDEX]-->", color="bright-green", end="")
            self.dprint("[❌]", color="bright-red")

            self.out_of_index = True
            return self.stream[-1], ""

    def emit(self, token_dict):
        # CHECKING FOR DUPLICATE ATTRIBUTES IN START TAG AND REMOVE FROM TOKEN BUFFER IF IT EXISTS
        if token_dict["token-type"] == "start-tag":
            try:
                unique_attr_names_list, unique_attrs_list = [], []
                for attr in token_dict["attributes"]:
                    attr_name = attr[0]
                    if attr_name not in unique_attr_names_list:
                        unique_attr_names_list.append(attr[0])
                        unique_attrs_list.append(attr)
                    else:
                        # GENERATE duplicate-attribute parse-error
                        self.generate_parse_error("DUPLICATE ATTRIBUTE")
                token_dict["attributes"] = unique_attrs_list
                self.output.append(token_dict)
            except KeyError:
                pass
        # END TAG
        elif token_dict["token-type"] == "end-tag":
            # DUPLICATE ATTRIBUTES PARSE ERROR
            unique_attr_names = []
            for attr in token_dict["attributes"]:
                if attr not in unique_attr_names:
                    unique_attr_names.append(attr)
                else:
                    self.generate_parse_error("DUPLICATE ATTRIBUTE")
                    break

            # REMOVE ATTRIBUTES FROM END TAG TOKEN
            if token_dict["attributes"]:
                self.generate_parse_error("END TAG WITH ATTRIBUTES")
                token_dict["attributes"] = []

            # SELF CLOSING END TAG, UNSET IT
            if token_dict["self-closing-flag"] == "set":
                token_dict["self-closing-flag"] = "unset"
                self.generate_parse_error("END TAG WITH TRAILING SOLIDUS")

            self.output.append(token_dict)
        # GROUPING CONSECUTIVE CHARACTER TOKENS
        # CHARACTER
        elif token_dict["token-type"] == "character":
            try:
                if self.output[-1]["token-type"] == "character":
                    self.output[-1]["data"] += token_dict["data"]
                else:
                    self.output.append(token_dict)
            except IndexError:
                self.output.append(token_dict)
        # TODO: TEMPORARILY BLOCKING EOF TYPE TOKEN
        # EOF
        elif token_dict["token-type"] == "eof":
            pass  # i.e ignore
        # ANYTHING ELSE
        # COMMENT | DOCTYPE
        else:
            self.output.append(token_dict)

        # EMPTY TOKEN BUFFER
        self.token_buffer = {}

    def flush_code_pt_consumed_as_char_ref(self):
        if self.consumed_as_part_of_an_attr():
            # append current temporary buffer to current attribute's value
            self.token_buffer["attributes"][-1][1] += self.temp_buffer
            return
        else:
            self.emit({
                "token-type": "character",
                "data": self.temp_buffer
            })
            return

    def generate_parse_error(self, error):
        self.parse_errors.append(error.lower().replace(" ", "-"))
        self.dprint(f"[PARSE ERROR]: [{error}]", debugging_mode=2, color="yellow")

    ###############################################################################################
    # CHECKS #
    def consumed_as_part_of_an_attr(self):
        # CHECKS IF THE RETURN STATE IS TO ANY ONE OF THE ATTRIBUTE STATES
        char_ref_in_attr = [
            self.attr_val_double_quote_state,
            self.attr_val_single_quote_state,
            self.attr_val_unquoted_state
        ]
        return self.return_state in char_ref_in_attr

    ###############################################################################################
    # STATES #
    """
    ################ DATA STATE ################
    STATUS: COMPLETE
    """
    def data_state(self):
        current_char, next_char = self.consume()
        # POSSIBLE BEGINNING OF AMPERSAND ENTITY (FOR EXAMPLE, &AElig;)
        if next_char == "&":
            self.return_state = self.data_state
            self.state = self.char_ref_state
            return
        # POSSIBLE BEGINNING OF A TAG
        elif next_char == "<":
            self.state = self.tag_open_state
            return
        # NULL CHARACTER
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error then emit current character as a character
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.emit({
                "token-type": "character",
                "data": next_char
            })
        # END OF FILE (EOF) ENCOUNTERED
        elif next_char == "":
            self.emit({
                "token-type": "eof"
            })
        else:
            self.emit({
                "token-type": "character",
                "data": next_char
            })
            return

    """
    ################ TAG OPEN STATE ################
    STATUS: COMPLETE
    """
    def tag_open_state(self):
        current_char, next_char = self.consume()
        # POSSIBLE <!DOCTYPE type> declaration or POSSIBLE COMMENT <!-- COMMENT -->
        if next_char == "!":
            self.state = self.markup_declaration_open_state
            return
        # POSSIBLE END TAG </tag-name>
        elif next_char == "/":
            self.state = self.end_tag_open_state
            return
        # POSSIBLE BEGINNING OF TAG <tag-name>
        elif inside(self.ascii_alpha, next_char):
            self.token_buffer = {
                "token-type": "start-tag",

                "tag-name": "",
                "self-closing-flag": "unset",
                # Attributes' value is a list in the below form with the last item being the current attribute
                # [[attr_name, attr_value],[attr_name, attr_value], [current_attr, current_attr_val]]
                "attributes": []
            }
            self.reconsuming = True
            self.state = self.tag_name_state
            return
        # BOGUS COMMENT BEGIN <?everything here is a comment until the closing angle bracket>
        elif next_char == "?":
            # GENERATE unexpected-question-mark-instead-of-tag-name parse-error
            self.generate_parse_error("UNEXPECTED QUESTION MARK INSTEAD OF TAG NAME")
            self.token_buffer = {
                "token-type": "comment",
                "data": ""
            }
            self.reconsuming = True
            self.state = self.bogus_comment_state
            return
        # END OF FILE (EOF) ENCOUNTERED
        elif next_char == "":
            # GENERATE eof-before-tag-name parse-error
            self.generate_parse_error("EOF BEFORE TAG NAME")
            self.emit({
                "token-type": "character",
                "data": "<"
            })
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE invalid-first-character-of-tag-name parse-error
            self.generate_parse_error("INVALID FIRST CHARACTER OF TAG NAME")
            self.emit({
                "token-type": "character",
                "data": "<"
            })
            self.reconsuming = True
            self.state = self.data_state
            return

    """
    ################ TAG NAME STATE ################
    STATUS: COMPLETE
    """
    def tag_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.before_attr_name_state
            return
        # SELF CLOSING TAG <br/>
        elif next_char == "/":
            self.state = self.self_closing_start_tag_state
            return
        elif next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif inside(self.ascii_upper_alpha, next_char):
            self.token_buffer["tag-name"] += next_char.lower()
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["tag-name"] += "\uFFFD"
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["tag-name"] += next_char
            return

    """
    ################ BEFORE ATTRIBUTE NAME STATE ################
    STATUS: COMPLETE
    """
    def before_attr_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # ignore
        elif next_char in ["/", ">", ""]:
            self.reconsuming = True
            self.state = self.after_attr_name_state
            return
        elif next_char == "=":
            # GENERATE unexpected-equals-sign-before-attribute-name parse-error
            self.generate_parse_error("UNEXPECTED EQUALS SIGN BEFORE ATTRIBUTE NAME")
            self.token_buffer["attributes"].append([next_char, ""])
            self.state = self.attr_name_state
            return
        else:
            self.token_buffer["attributes"].append(["", ""])
            self.reconsuming = True
            self.state = self.attr_name_state
            return

    """
    ################ ATTRIBUTE NAME STATE ################
    STATUS: COMPLETE
    """
    def attr_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " ", "/", ">", ""]:
            self.reconsuming = True
            self.state = self.after_attr_name_state
            return
        elif next_char == "=":
            self.state = self.before_attr_val_state
            return
        elif inside(self.ascii_upper_alpha, next_char):
            self.token_buffer["attributes"][-1][0] += next_char.lower()
            return
        elif next_char in "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")

            # self.token_buffer["attributes"][-1][0] is the current attribute name
            self.token_buffer["attributes"][-1][0] += "\uFFFD"  # REPLACEMENT CHARACTER
            return
        # MISSING =, i.e. <element attr_name" or <element _name' or <element attr_name<
        elif next_char in ['"', "'", "<"]:
            # GENERATE unexpected-character-in-attribute-name parse-error
            self.generate_parse_error("UNEXPECTED CHARACTER IN ATTRIBUTE NAME")
            # same treatment as the else block but generate parse error

            # self.token_buffer["attributes"][-1][0] is the current attribute name
            self.token_buffer["attributes"][-1][0] += next_char
            return
        else:
            # self.token_buffer["attributes"][-1][0] is the current attribute name
            self.token_buffer["attributes"][-1][0] += next_char
            return

    """
    ################ BEFORE ATTRIBUTE VALUE STATE ################
    STATUS: COMPLETE
    CASES: 5
    """
    def before_attr_val_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore these characters
        elif next_char == '"':
            self.state = self.attr_val_double_quote_state
            return
        elif next_char == "'":
            self.state = self.attr_val_single_quote_state
            return
        elif next_char == ">":
            self.generate_parse_error("MISSING ATTRIBUTE VALUE")
            self.state = self.data_state
            self.emit(self.token_buffer)
            return
        else:
            self.reconsuming = True
            self.state = self.attr_val_unquoted_state
            return

    """
    ################ MARKUP DECLARATION OPEN STATE ################
    STATUS: INCOMPLETE
    CASES: 3
    """
    def markup_declaration_open_state(self):
        i = self.index
        self.consume()

        # COMMENT BEGINNING <!--
        if self.stream[i:i+2] == "--":
            # CONSUME ONE MORE CHARACTER TO COMPENSATE FOR THE SECOND HYPHEN (-)
            self.consume()
            self.token_buffer = {
                "token-type": "comment",
                "data": ""
            }
            self.state = self.comment_start_state
            return
        # DOCTYPE DECLARATION <!DOCTYPE
        elif self.stream[i:i+7].upper() == "DOCTYPE":
            # COMPENSATE INDEX FOR THE DOCTYPE
            self.index += 6
            self.state = self.doctype_state
            return
        # [CDATA[
        elif self.stream[i:i+7] == "[CDATA[":
            # TODO: THE TOKENIZER IS CURRENTLY IGNORING [CDATA[ IMPLEMENT CDATA
            return
        else:
            # GENERATE incorrectly-opened-comment parse-error
            self.generate_parse_error("INCORRECTLY OPENED COMMENT")

            self.token_buffer = {
                "token-type": "comment",
                "data": ""
            }
            self.reconsuming = True
            self.state = self.bogus_comment_state
            return

    """
    ################ COMMENT START STATE ################
    STATUS: COMPLETE
    """
    def comment_start_state(self):
        current_char, next_char = self.consume()

        if next_char == "-":
            self.state = self.comment_start_dash_state
            return
        elif next_char == ">":
            # GENERATE abrupt-closing-of-empty-comment parse-error
            self.generate_parse_error("ABRUPT CLOSING OF EMPTY COMMENT")
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        else:
            self.reconsuming = True
            self.out_of_index = False
            self.state = self.comment_state
            return

    """
    ################ COMMENT START DASH STATE ################
    STATUS: COMPLETE
    """
    def comment_start_dash_state(self):
        current_char, next_char = self.consume()

        # <!-- COMMENT --
        if next_char == "-":
            self.state = self.comment_end_state
            return
        # <!-- COMMENT ->
        elif next_char == ">":
            # GENERATE abrupt-closing-of-empty-comment parse-error
            self.generate_parse_error("ABRUPT CLOSING OF EMPTY COMMENT")
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        # <!-- COMMENT
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN COMMENT")

            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
        else:
            self.token_buffer["data"] += "-"
            self.reconsuming = True
            self.state = self.comment_state
            return

    """
    ################ COMMENT STATE ################
    STATUS: COMPLETE
    """
    def comment_state(self):
        current_char, next_char = self.consume()

        # <!-- COMMENT<
        if next_char == "<":
            self.token_buffer["data"] += next_char
            self.state = self.comment_less_than_sign_state
            return
        elif next_char == "-":
            self.state = self.comment_end_dash_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")

            self.token_buffer["data"] += "\uFFFD"  # REPLACEMENT CHARACTER
            return
        elif next_char == "":
            self.generate_parse_error("EOF IN COMMENT")
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
        else:
            self.token_buffer["data"] += next_char
            return

    """
    ################ COMMENT LESS THAN SIGN STATE ################
    STATUS: COMPLETE
    """
    def comment_less_than_sign_state(self):
        current_char, next_char = self.consume()

        if next_char == "!":
            self.token_buffer["data"] += next_char
            self.state = self.comment_less_than_sign_bang_state
            return
        elif next_char == "<":
            self.token_buffer["data"] += next_char
            return
        else:
            self.reconsuming = True
            self.state = self.comment_state
            return

    """
    ################ COMMENT LESS THAN SIGN BANG STATE ################
    STATUS: COMPLETE
    """
    def comment_less_than_sign_bang_state(self):
        current_char, next_char = self.consume()

        if next_char == "-":
            self.state = self.comment_less_than_sign_bang_dash_state
            return
        else:
            self.reconsuming = True
            self.state = self.comment_state
            return

    """
    ################ COMMENT LESS THAN SIGN BANG DASH STATE ################
    STATUS: COMPLETE
    """
    def comment_less_than_sign_bang_dash_state(self):
        current_char, next_char = self.consume()

        if next_char == "-":
            self.state = self.comment_less_than_sign_bang_dash_dash_state
            return
        else:
            self.reconsuming = True
            self.state = self.comment_end_dash_state
            return

    """
    ################ COMMENT LESS THAN SIGN BANG DASH DASH STATE ################
    STATUS: COMPLETE
    """
    def comment_less_than_sign_bang_dash_dash_state(self):
        current_char, next_char = self.consume()

        if next_char == ">":
            self.reconsuming = True
            self.state = self.comment_end_state
            return
        elif next_char == "":
            self.out_of_index = False
            self.state = self.comment_end_state
            return
        else:
            # GENERATE nested-comment parse-error
            self.generate_parse_error("NESTED COMMENT")
            self.reconsuming = True
            self.state = self.comment_end_state
            return

    """
    ################ COMMENT END DASH STATE ################
    STATUS: COMPLETE
    """
    def comment_end_dash_state(self):
        current_char, next_char = self.consume()

        if next_char == "-":
            self.state = self.comment_end_state
            return
        elif next_char == "":
            # GENERATE eof-in-comment parse-error
            self.generate_parse_error("EOF IN COMMENT")
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["data"] += "-"
            self.reconsuming = True
            self.state = self.comment_state
            return

    """
    ################ COMMENT END STATE ################
    STATUS: COMPLETE
    """
    def comment_end_state(self):
        current_char, next_char = self.consume()

        if next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "!":
            self.state = self.comment_end_bang_state
            return
        elif next_char == "-":
            self.token_buffer["data"] += "-"
            return
        elif next_char == "":
            # GENERATE eof-in-comment parse-error
            self.generate_parse_error("EOF IN COMMENT")
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["data"] += "--"
            self.reconsuming = True
            self.state = self.comment_state
            return

    """
    ################ COMMENT END BANG STATE ################
    STATUS: COMPLETE
    """
    def comment_end_bang_state(self):
        current_char, next_char = self.consume()

        if next_char == "-":
            self.token_buffer["data"] += "--!"
            self.state = self.comment_end_dash_state
            return
        elif next_char == ">":
            # GENERATE incorrectly-closed-comment parse-error
            self.generate_parse_error("INCORRECTLY CLOSED COMMENT")
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-comment parse-error
            self.generate_parse_error("EOF IN COMMENT")
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["data"] += "--!"
            self.reconsuming = True
            self.state = self.comment_state
            return

    """
    ################ DOCTYPE STATE ################
    STATUS: COMPLETE
    """
    def doctype_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.before_doctype_name_state
            return
        elif next_char == ">":
            self.reconsuming = True
            self.state = self.before_doctype_name_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer = {
                "token-type": "DOCTYPE",
                "name": "missing",
                "public-identifier": "missing",
                "system-identifier": "missing",
                "force-quirks": True
            }
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE missing-whitespace-before-doctype-name parse-error
            self.generate_parse_error("MISSING WHITESPACE BEFORE DOCTYPE NAME")
            self.reconsuming = True
            self.state = self.before_doctype_name_state
            return

    """
    ################ BEFORE DOCTYPE NAME STATE ################
    STATUS: COMPLETE
    """
    def before_doctype_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore these characters
        elif inside(self.ascii_upper_alpha, next_char):
            self.token_buffer = {
                "token-type": "DOCTYPE",
                "name": next_char.lower(),
                "public-identifier": "missing",
                "system-identifier": "missing",
                "force-quirks": False
            }
            self.state = self.doctype_name_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer = {
                "token-type": "DOCTYPE",
                "name": "\uFFFD",
                "public-identifier": "missing",
                "system-identifier": "missing",
                "force-quirks": False
            }
            self.state = self.doctype_name_state
            return
        elif next_char == ">":
            # GENERATE missing-doctype-name parse-error
            self.generate_parse_error("MISSING DOCTYPE NAME")
            self.token_buffer = {
                "token-type": "DOCTYPE",
                "name": "missing",
                "public-identifier": "missing",
                "system-identifier": "missing",
                "force-quirks": True
            }
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer = {
                "token-type": "DOCTYPE",
                "name": "missing",
                "public-identifier": "missing",
                "system-identifier": "missing",
                "force-quirks": True
            }
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer = {
                "token-type": "DOCTYPE",
                "name": next_char,
                "public-identifier": "missing",
                "system-identifier": "missing",
                "force-quirks": False
            }

            self.state = self.doctype_name_state
            return

    """
    ################ DOCTYPE NAME STATE ################
    STATUS: COMPLETE
    """
    def doctype_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.after_doctype_name_state
            return
        elif next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif inside(self.ascii_upper_alpha, next_char):
            self.token_buffer["name"] += next_char.lower()
            return
        elif next_char == "\0":
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["name"] += "\uFFFD"
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["name"] += next_char
            return

    """
    ################ AFTER DOCTYPE NAME STATE ################
    STATUS: COMPLETE
    """
    def after_doctype_name_state(self):
        i = self.index
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore these characters
        elif next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            if self.stream[i:i+6].upper() == "PUBLIC":
                self.index += 5  # compensating for skipping PUBLIC consumption char by char
                self.state = self.after_doctype_public_keyword_state
                return
            elif self.stream[i:i+6].upper() == "SYSTEM":
                self.index += 5  # compensating for skipping SYSTEM consumption char by char
                self.state = self.after_doctype_system_keyword_state
                return
            else:
                # GENERATE invalid-character-sequence-after-doctype-name parse-error
                self.generate_parse_error("INVALID CHARACTER SEQUENCE AFTER DOCTYPE NAME")
                self.token_buffer["force-quirks"] = True
                self.reconsuming = True
                self.state = self.bogus_doctype_state
                return

    """
    ################ AFTER DOCTYPE PUBLIC KEYWORD STATE ################
    STATUS: COMPLETE
    """
    def after_doctype_public_keyword_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.before_doctype_public_identifier_state
            return
        elif next_char == '"':
            # GENERATE missing-whitespace-after-doctype-public-keyword parse-error
            self.generate_parse_error("MISSING WHITESPACE AFTER DOCTYPE PUBLIC KEYWORD")
            self.token_buffer["public-identifier"] = ""
            self.state = self.doctype_public_identifier_double_quoted_state
            return
        elif next_char == "'":
            # GENERATE missing-whitespace-after-doctype-public-keyword parse-error
            self.generate_parse_error("MISSING WHITESPACE AFTER DOCTYPE PUBLIC KEYWORD")
            self.token_buffer["public-identifier"] = ""
            self.state = self.doctype_public_identifier_single_quoted_state
            return
        elif next_char == ">":
            # GENERATE missing-doctype-public-identifier parse-error
            self.generate_parse_error("MISSING DOCTYPE PUBLIC IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE missing-quote-before-doctype-public-identifier parse-error
            self.generate_parse_error("MISSING QUOTE BEFORE DOCTYPE PUBLIC IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.reconsuming = True
            self.state = self.bogus_doctype_state
            return
    """
    ################ BEFORE DOCTYPE PUBLIC IDENTIFIER STATE ################
    STATUS: COMPLETE
    """
    def before_doctype_public_identifier_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore the character
        elif next_char == '"':
            self.token_buffer["public-identifier"] = ""
            self.state = self.doctype_public_identifier_double_quoted_state
            return
        elif next_char == "'":
            self.token_buffer["public-identifier"] = ""
            self.state = self.doctype_public_identifier_single_quoted_state
            return
        elif next_char == ">":
            # GENERATE missing-doctype-public-identifier parse-error
            self.generate_parse_error("MISSING DOCTYPE PUBLIC IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE missing-quote-before-doctype-public-identifier parse-error
            self.generate_parse_error("MISSING QUOTE BEFORE DOCTYPE PUBLIC IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.reconsuming = True
            self.state = self.bogus_doctype_state
            return

    """
    ################ DOCTYPE PUBLIC IDENTIFIER DOUBLE QUOTED STATE ################
    STATUS: COMPLETE
    """
    def doctype_public_identifier_double_quoted_state(self):
        current_char, next_char = self.consume()

        if next_char == '"':
            self.state = self.after_doctype_public_identifier_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["public-identifier"] += "\uFFFD"
            return
        elif next_char == ">":
            # GENERATE abrupt-doctype-public-identifier parse-error
            self.generate_parse_error("ABRUPT DOCTYPE PUBLIC IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["public-identifier"] += next_char
            return

    """
    ################ DOCTYPE PUBLIC IDENTIFIER SINGLE QUOTED STATE ################
    STATUS: COMPLETE
    """

    def doctype_public_identifier_single_quoted_state(self):
        current_char, next_char = self.consume()

        if next_char == "'":
            self.state = self.after_doctype_public_identifier_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["public-identifier"] += "\uFFFD"
            return
        elif next_char == ">":
            # GENERATE abrupt-doctype-public-identifier parse-error
            self.generate_parse_error("ABRUPT DOCTYPE PUBLIC IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["public-identifier"] += next_char
            return

    """
    ################ AFTER DOCTYPE PUBLIC IDENTIFIER STATE ################
    STATUS: COMPLETE
    """
    def after_doctype_public_identifier_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.between_doctype_public_and_system_identifiers_state
            return
        elif next_char == '>':
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == '"':
            # GENERATE missing-whitespace-between-doctype-public-and-system-identifiers parse-error
            self.generate_parse_error("MISSING WHITESPACE BETWEEN DOCTYPE PUBLIC AND SYSTEM IDENTIFIERS")
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_double_quoted_state
            return
        elif next_char == "'":
            # GENERATE missing-whitespace-between-doctype-public-and-system-identifiers parse-error
            self.generate_parse_error("MISSING WHITESPACE BETWEEN DOCTYPE PUBLIC AND SYSTEM IDENTIFIERS")
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_single_quoted_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE missing-quote-before-doctype-system-identifier parse-error
            self.generate_parse_error("MISSING QUOTE BEFORE DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.reconsuming = True
            self.state = self.bogus_doctype_state
            return

    """
    ################ BETWEEN DOCTYPE PUBLIC AND SYSTEM IDENTIFIERS STATE ################
    STATUS: COMPLETE
    """
    def between_doctype_public_and_system_identifiers_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore the character
        elif next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == '"':
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_double_quoted_state
            return
        elif next_char == "'":
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_single_quoted_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE missing-quote-before-doctype-system-identifier parse-error
            self.generate_parse_error("MISSING QUOTE BEFORE DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.reconsuming = True
            self.state = self.bogus_doctype_state
            return

    """
    ################ AFTER DOCTYPE SYSTEM KEYWORD STATE ################
    STATUS: COMPLETE
    """
    def after_doctype_system_keyword_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.before_doctype_system_identifier_state
            return
        elif next_char == '"':
            # GENERATE missing-whitespace-after-doctype-system-keyword parse-error
            self.generate_parse_error("MISSING WHITESPACE AFTER DOCTYPE SYSTEM KEYWORD")
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_double_quoted_state
            return
        elif next_char == "'":
            # GENERATE missing-whitespace-after-doctype-system-keyword parse-error
            self.generate_parse_error("MISSING WHITESPACE AFTER DOCTYPE SYSTEM KEYWORD")
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_single_quoted_state
            return
        elif next_char == ">":
            # GENERATE missing-doctype-system-identifier parse-error
            self.generate_parse_error("MISSING DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE missing-quote-before-doctype-system-identifier parse-error
            self.generate_parse_error("MISSING QUOTE BEFORE DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.reconsuming = True
            self.state = self.bogus_doctype_state
            return

    """
    ################ BEFORE DOCTYPE SYSTEM IDENTIFIER STATE ################
    STATUS: COMPLETE
    """
    def before_doctype_system_identifier_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore the character
        elif next_char == '"':
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_double_quoted_state
            return
        elif next_char == "'":
            self.token_buffer["system-identifier"] = ""
            self.state = self.doctype_system_identifier_single_quoted_state
            return
        elif next_char == ">":
            # GENERATE missing-doctype-system-identifier parse-error
            self.generate_parse_error("MISSING DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE missing-quote-before-doctype-system-identifier parse-error
            self.generate_parse_error("MISSING QUOTE BEFORE DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.reconsuming = True
            self.state = self.bogus_doctype_state
            return

    """
    ################ DOCTYPE SYSTEM IDENTIFIER DOUBLE QUOTED STATE ################
    STATUS: COMPLETE
    """
    def doctype_system_identifier_double_quoted_state(self):
        current_char, next_char = self.consume()

        if next_char == '"':
            self.state = self.after_doctype_system_identifier_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["system-identifier"] += "\uFFFD"
            return
        elif next_char == ">":
            # GENERATE abrupt-doctype-system-identifier parse-error
            self.generate_parse_error("ABRUPT DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["system-identifier"] += next_char
            return

    """
    ################ DOCTYPE SYSTEM IDENTIFIER SINGLE QUOTED STATE ################
    STATUS: COMPLETE
    """
    def doctype_system_identifier_single_quoted_state(self):
        current_char, next_char = self.consume()

        if next_char == "'":
            self.state = self.after_doctype_system_identifier_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["system-identifier"] += "\uFFFD"
            return
        elif next_char == ">":
            # GENERATE abrupt-doctype-system-identifier parse-error
            self.generate_parse_error("ABRUPT DOCTYPE SYSTEM IDENTIFIER")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["system-identifier"] += next_char
            return

    """
    ################ AFTER DOCTYPE SYSTEM IDENTIFIER STATE ################
    STATUS: COMPLETE
    """
    def after_doctype_system_identifier_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore the character
        elif next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-in-doctype parse-error
            self.generate_parse_error("EOF IN DOCTYPE")
            self.token_buffer["force-quirks"] = True
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE unexpected-character-after-doctype-system-identifier parse-error
            self.generate_parse_error("UNEXPECTED CHARACTER AFTER DOCTYPE SYSTEM IDENTIFIER")
            self.reconsuming = True
            self.state = self.bogus_doctype_state
            return

    """
    ################ BOGUS DOCTYPE STATE ################
    STATUS: COMPLETE
    """
    def bogus_doctype_state(self):
        current_char, next_char = self.consume()

        if next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            return  # i.e. ignore the character
        elif next_char == "":
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            return  # i.e. ignore the character

    """
    ################ END TAG OPEN STATE ################
    STATUS: COMPLETE
    """
    def end_tag_open_state(self):
        current_char, next_char = self.consume()

        if inside(self.ascii_alpha, next_char):
            self.token_buffer = {
                "token-type": "end-tag",
                "tag-name": "",
                "self-closing-flag": "unset",
                "attributes": []
            }
            self.reconsuming = True
            self.state = self.tag_name_state
            return
        elif next_char == ">":
            # GENERATE missing-end-tag-name parse-error
            self.generate_parse_error("MISSING END TAG NAME")
            self.state = self.data_state
            return
        elif next_char == "":
            # GENERATE eof-before-tag-name parse-error
            self.generate_parse_error("EOF BEFORE TAG NAME")
            self.emit({
                "token-type": "character",
                "data": "<"
            })
            self.emit({
                "token-type": "character",
                "data": "/"
            })
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE invalid-first-character-of-tag-name parse-error
            self.generate_parse_error("INVALID FIRST CHARACTER OF TAG NAME")
            self.token_buffer = {
                "token-type": "comment",
                "data": ""
            }
            self.reconsuming = True
            self.state = self.bogus_comment_state
            return

    """
    ################ CHARACTER REFERENCE STATE ################
    STATUS: INCOMPLETE
    CASES: 1
    """
    def char_ref_state(self):
        # TODO: FINISH REST OF THE CASES
        current_char, next_char = self.consume()
        self.temp_buffer = ""  # empty the buffer in-case characters left from previous operations
        self.temp_buffer = "&"
        if inside(self.ascii_alphanumeric, next_char):
            self.state = self.named_char_ref_state
            self.reconsuming = True
        elif next_char == "#":
            self.temp_buffer += "#"
            self.state = self.numeric_char_ref_state
            return
        else:
            self.flush_code_pt_consumed_as_char_ref()
            self.reconsuming = True
            self.state = self.return_state
            return

    """
    ################ NUMERIC CHARACTER REFERENCE STATE ################
    STATUS: COMPLETE
    """
    def numeric_char_ref_state(self):
        self.temp_buffer = "0"
        self.char_ref_code_buffer = 0
        current_char, next_char = self.consume()

        if next_char.lower() == "x":
            self.temp_buffer += next_char
            self.state = self.hexadecimal_char_ref_start_state
            return
        else:
            self.reconsuming = True
            self.state = self.decimal_char_ref_start_state
            return

    """
    ################ HEXADECIMAL CHARACTER REFERENCE START STATE ################
    STATUS: COMPLETE
    """
    def hexadecimal_char_ref_start_state(self):
        current_char, next_char = self.consume()

        if inside(self.ascii_hex_digit, next_char):
            self.reconsuming = True
            self.state = self.hexadecimal_char_ref_state
            return
        else:
            self.generate_parse_error("ABSENCE OF DIGITS IN NUMERIC CHARACTER REFERENCE STATE")
            self.flush_code_pt_consumed_as_char_ref()
            self.state = self.return_state
            return

    """
    ################ DECIMAL CHARACTER REFERENCE START STATE ################
    STATUS: COMPLETE
    """
    def decimal_char_ref_start_state(self):
        current_char, next_char = self.consume()

        if inside(self.ascii_digit, next_char):
            self.reconsuming = True
            self.state = self.decimal_char_ref_state
            return
        else:
            self.generate_parse_error("ABSENCE OF DIGITS IN NUMERIC CHARACTER REFERENCE STATE")
            self.flush_code_pt_consumed_as_char_ref()
            self.state = self.return_state
            return

    """
    ################ HEXADECIMAL CHARACTER REFERENCE STATE ################
    STATUS: COMPLETE
    """
    def hexadecimal_char_ref_state(self):
        current_char, next_char = self.consume()

        if inside(self.ascii_digit, next_char):
            self.char_ref_code_buffer *= 16
            self.char_ref_code_buffer += int(next_char)
            return
        elif inside(self.ascii_hex_digit, next_char):
            self.char_ref_code_buffer *= 16
            self.char_ref_code_buffer += int(next_char, base=16)
            return
        elif next_char == ";":
            self.state = self.numeric_char_ref_end_state
            return
        else:
            self.generate_parse_error("MISSING SEMICOLON AFTER CHARACTER REFERENCE")
            self.reconsuming = True
            self.state = self.numeric_char_ref_end_state
            return

    """
    ################ DECIMAL CHARACTER REFERENCE STATE ################
    STATUS: COMPLETE
    """
    def decimal_char_ref_state(self):
        current_char, next_char = self.consume()

        if inside(self.ascii_digit, next_char):
            self.char_ref_code_buffer *= 10
            self.char_ref_code_buffer += int(next_char)
            return
        elif next_char == ";":
            self.state = self.numeric_char_ref_end_state
            return
        else:
            self.generate_parse_error("MISSING SEMICOLON AFTER CHARACTER REFERENCE")
            self.reconsuming = True
            self.state = self.numeric_char_ref_end_state
            return

    """
    ################ NUMERIC CHARACTER REFERENCE END STATE ################
    STATUS: COMPLETE
    """
    def numeric_char_ref_end_state(self):
        # noinspection PyTypeChecker
        self.char_ref_code_buffer = hex(self.char_ref_code_buffer)
        if self.char_ref_code_buffer == "0x0":
            self.generate_parse_error("NULL CHARACTER REFERENCE")
            self.char_ref_code_buffer = "0xFFFD"
        elif int(self.char_ref_code_buffer, base=16) > 1114111:
            self.generate_parse_error("CHARACTER REFERENCE OUTSIDE UNICODE RANGE")
            self.char_ref_code_buffer = "0xFFFD"
        # TODO: IMPLEMENT SURROGATE CASE IN NUMERIC CHAR REF END STATE
        elif inside(self.non_characters, self.char_ref_code_buffer):
            self.generate_parse_error("NONCHARACTER CHARACTER REFERENCE")
        elif inside(self.control_characters, self.char_ref_code_buffer) \
                and self.char_ref_code_buffer not in self.whitespace \
                or self.char_ref_code_buffer == "0x0D":
            self.generate_parse_error("CONTROL CHARACTER REFERENCE")
        elif inside(self.special_numeric_entities_table, self.char_ref_code_buffer):
            self.char_ref_code_buffer = self.special_numeric_entities_table[self.char_ref_code_buffer]

        self.temp_buffer = str(chr(int(self.char_ref_code_buffer, base=16)))
        self.flush_code_pt_consumed_as_char_ref()
        self.state = self.return_state
        return

    """
    ################ NAMED CHARACTER REFERENCE STATE ################
    STATUS: COMPLETE
    """
    def named_char_ref_state(self):
        name_table_str = "\n".join(self.ampersand_table.keys())  # name section of ampersand table
        stream_backtrack = None  # index to backtrack to if necessary
        buffer_backtrack = None  # buffer's index to backtrack to

        semicolon_error = False  # flag to to keep track of whether to generate missing semicolon parse error or not

        while self.index < len(self.stream):
            current_char, next_char = self.consume()
            self.temp_buffer += next_char

            if inside(self.ascii_alphanumeric, next_char):
                # LAST VALID MATCH
                if self.temp_buffer + "\n" in name_table_str:
                    stream_backtrack = self.index
                    buffer_backtrack = len(self.temp_buffer)

            # FIRST NON ALPHANUMERIC ENCOUNTERED [STOP CONSUMING NOW]
            else:
                # INVALID END, TO BE CONSUMED IN THE RETURN STATE
                if next_char != ";":
                    self.temp_buffer = self.temp_buffer[:-1]
                    self.reconsuming = True
                    self.dprint(f"=>[INVALID ENDING OF LIGATURE]: [{self.temp_buffer}]", debugging_mode=3,
                                color="yellow")

                if self.temp_buffer[:-1] + ";\n" not in name_table_str:
                    if not self.consumed_as_part_of_an_attr():
                        # REVERT POSSIBLE AND REQUIRED
                        if stream_backtrack is not None and buffer_backtrack is not None:
                            self.index = stream_backtrack
                            self.temp_buffer = self.temp_buffer[:buffer_backtrack]
                            self.dprint(f"=>[REVERTING BACK TO]: [{self.temp_buffer}]", debugging_mode=3,
                                        color="green")
                            semicolon_error = True
                            break
                        # REVERT REQUIRED BUT NOT POSSIBLE
                        self.dprint(f"=>[REVERTING REQUIRED BUT NOT POSSIBLE]: [{self.temp_buffer}]", debugging_mode=3,
                                    color="green")
                break

        ############################################
        # CHECK IF THE FINAL MATCH IS VALID OR NOT #
        valid = False  # invalid by default

        # LAST CHARACTER IS NOT ; OR ANY OTHER SYMBOL
        if self.temp_buffer[-1] in self.ascii_alphanumeric:

            # NOT MENTIONED BUT I THINK ONE REVERT IS NOT REQUIRED WHEN IN CONSUMED AS PART OF AN ATTRIBUTE
            if not self.consumed_as_part_of_an_attr():
                # REVERT POSSIBLE AND REQUIRED
                if stream_backtrack is not None and buffer_backtrack is not None:
                    self.index = stream_backtrack
                    self.temp_buffer = self.temp_buffer[:buffer_backtrack]
                    self.dprint(f"=>[REVERTING BACK TO]: [{self.temp_buffer}]", debugging_mode=3,
                                color="green")
                    semicolon_error = True
                # REVERT REQUIRED BUT NOT POSSIBLE
                self.dprint(f"=>[REVERTING REQUIRED BUT NOT POSSIBLE]: [{self.temp_buffer}]", debugging_mode=3,
                            color="green")
            # CHECK VALIDITY NOW
            if self.temp_buffer in self.ampersand_table.keys():
                valid = True
                semicolon_error = True
        # LAST CHARACTER IS EITHER ; OR ANY OTHER SYMBOL
        else:
            # CHECK VALIDITY
            if self.temp_buffer[:-1] + ";" in self.ampersand_table.keys():
                valid = True

        #####################
        # VALID MATCH FOUND #
        if valid:
            self.dprint(f"=>[VALID LIGATURE FOUND]: [{self.temp_buffer}]", debugging_mode=3, color="green")
            current_char, next_char = self.consume()
            self.reconsuming = True

            if self.consumed_as_part_of_an_attr() and self.temp_buffer[-1] != ";"\
                    and inside(self.ascii_alphanumeric + "=", next_char):
                # REMOVE UNEXPECTED ENDING
                if self.temp_buffer[-1] not in self.ascii_alphanumeric and self.temp_buffer != ";":
                    self.temp_buffer = self.temp_buffer[:-1]
                self.flush_code_pt_consumed_as_char_ref()
                self.state = self.return_state
                return
            else:
                try:
                    self.temp_buffer = self.ampersand_table[self.temp_buffer]["characters"]
                except KeyError:
                    self.temp_buffer = self.ampersand_table[self.temp_buffer[:-1] + ";"]["characters"]
                    semicolon_error = True

                if semicolon_error:
                    self.generate_parse_error("MISSING SEMICOLON AFTER CHARACTER REFERENCE")
                self.flush_code_pt_consumed_as_char_ref()
                self.state = self.return_state
                return
        #######################
        # INVALID MATCH FOUND #
        else:
            if semicolon_error:
                self.generate_parse_error("MISSING SEMICOLON AFTER CHARACTER REFERENCE")
            self.dprint(f"=>[NO VALID LIGATURE FOUND]: [{self.temp_buffer}]", debugging_mode=3, color="red")
            self.flush_code_pt_consumed_as_char_ref()
            self.state = self.ambiguous_ampersand_state
            return

    """
    ################ AMBIGUOUS AMPERSAND STATE ################
    STATUS: COMPLETE
    """
    def ambiguous_ampersand_state(self):
        current_char, next_char = self.consume()
        if inside(self.ascii_alphanumeric, next_char):
            if self.consumed_as_part_of_an_attr():
                pass  # append current_char to current attribute's value
            else:
                self.emit({
                    "token-type": "character",
                    "data": next_char
                })
        # SPECS SAY TO CHECK NEXT_CHAR AGAINST ";" BUT HERE SEEMS MORE APPROPRIATE TO CHECK AGAINST TEMP BUFFER
        # SINCE THE SEMICOLON IS ALREADY CONSUMED IN THE NAMED CHARACTER REFERENCE STATE
        elif self.temp_buffer[-1] == ";":
            if not self.consumed_as_part_of_an_attr():
                # GENERATE unknown-named-character-reference parse-error
                self.generate_parse_error("UNKNOWN NAMED CHARACTER REFERENCE")
            self.reconsuming = True
            self.state = self.return_state
        else:
            self.reconsuming = True
            self.state = self.return_state

    """
    ################ ATTRIBUTE VALUE DOUBLE QUOTE STATE ################
    STATUS: COMPLETE
    """
    def attr_val_double_quote_state(self):
        current_char, next_char = self.consume()

        if next_char == '"':
            self.state = self.after_attr_val_quoted_state
            return
        elif next_char == "&":
            self.return_state = self.attr_val_double_quote_state
            self.state = self.char_ref_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")

            self.token_buffer["attributes"][-1][1] += "\uFFFD"  # REPLACEMENT CHARACTER
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")

            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["attributes"][-1][1] += next_char
            return

    """
    ################ ATTRIBUTE VALUE SINGLE QUOTE STATE ################
    STATUS: COMPLETE
    """
    def attr_val_single_quote_state(self):
        current_char, next_char = self.consume()

        if next_char == "'":
            self.state = self.after_attr_val_quoted_state
            return
        elif next_char == "&":
            self.return_state = self.attr_val_single_quote_state
            self.state = self.char_ref_state
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")

            self.token_buffer["attributes"][-1][1] += "\uFFFD"  # REPLACEMENT CHARACTER
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")

            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["attributes"][-1][1] += next_char
            return

    """
    ################ ATTRIBUTE VALUE UNQUOTED STATE ################
    STATUS: COMPLETE
    """
    def attr_val_unquoted_state(self):
        current_char, next_char = self.consume()

        # Empty attribute value <element attr= > or New attribute <element attr=value new_attr=new_val> on whitespace
        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.before_attr_name_state
            return
        elif next_char == "&":
            self.return_state = self.attr_val_unquoted_state
            self.state = self.char_ref_state
            return
        elif next_char == ">":
            self.state = self.data_state
            self.emit(self.token_buffer)
            return
        elif next_char == "\0":
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["attributes"][-1][1] += "\uFFFD"
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")

            self.emit({
                "token-type": "eof"
            })
            return
        # same treatment as the else block except generate parse error
        elif next_char in ['"', "'", "<", "=", "`"]:
            # GENERATE unexpected-character-in-unquoted-attribute-value parse-error
            self.generate_parse_error("UNEXPECTED CHARACTER IN UNQUOTED ATTRIBUTE VALUE")

            # append character to current attribute's value
            self.token_buffer["attributes"][-1][1] += next_char
            return
        else:
            # append character to current attribute's value
            self.token_buffer["attributes"][-1][1] += next_char
            return

    """
    ################ AFTER ATTRIBUTE VALUE QUOTED STATE ################
    STATUS: COMPLETE
    """
    def after_attr_val_quoted_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            self.state = self.before_attr_name_state
            return
        elif next_char == "/":
            self.state = self.self_closing_start_tag_state
            return
        elif next_char == ">":
            self.state = self.data_state
            self.emit(self.token_buffer)
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")
            self.token_buffer = {
                "token-type": "eof"
            }
            self.emit(self.token_buffer)
        else:
            # GENERATE missing-whitespace-between-attributes parse-error
            self.generate_parse_error("MISSING WHITESPACE BETWEEN ATTRIBUTES")

            self.reconsuming = True
            self.state = self.before_attr_name_state
            return

    """
    ################ AFTER ATTRIBUTE NAME STATE ################
    STATUS: COMPLETE
    """
    def after_attr_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\n", "\f", " "]:
            return  # i.e. ignore the character
        elif next_char == "/":
            self.state = self.self_closing_start_tag_state
            return
        elif next_char == "=":
            self.state = self.before_attr_val_state
            return
        elif next_char == ">":
            self.state = self.data_state
            self.emit(self.token_buffer)
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")

            self.emit({
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["attributes"].append(["", ""])
            self.reconsuming = True
            self.state = self.attr_name_state
            return

    """
    ################ SELF CLOSING START TAG STATE ################
    STATUS: COMPLETE
    """
    def self_closing_start_tag_state(self):
        current_char, next_char = self.consume()

        if next_char == ">":
            self.token_buffer["self-closing-flag"] = "set"
            self.state = self.data_state
            self.emit(self.token_buffer)
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")
            self.emit({
                "token-type": "eof"
            })
            return
        else:
            # GENERATE unexpected-solidus-in-tag parse-error
            self.generate_parse_error("UNEXPECTED SOLIDUS IN TAG")
            self.reconsuming = True
            self.state = self.before_attr_name_state
            return

    """
    ################ BOGUS COMMENT STATE ################
    STATUS: COMPLETE
    """
    def bogus_comment_state(self):
        current_char, next_char = self.consume()

        if next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char == "":
            self.emit(self.token_buffer)
            self.emit({
                "token-type": "eof"
            })
            return
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["data"] += "\uFFFD"
        else:
            self.token_buffer["data"] += next_char

    ###############################################################################################
    # MAIN RUNTIME #
    def tokenize(self):
        if not self.empty_stream:
            while not self.out_of_index and not self.empty_stream:
                # DEBUGGING #
                state_name = self.state.__name__.upper().replace('_', ' ')
                self.dprint(f"[{state_name}]: ", color="magenta", end="")
                # DEBUGGING OVER #
                self.state()
                if self.reconsuming and self.out_of_index:
                    self.reconsuming = False
                    self.out_of_index = False

        # TOKENIZING OVER DEBUG PRINT
        self.dprint("###### TOKENIZER DONE TOKENIZING ######")
        # check for tokens that were not emitted and are still in the token_buffer
        if self.token_buffer != {}:
            self.emit(self.token_buffer)

        # FINAL OUTPUT
        output = str(self.output).encode("utf8").decode("utf8").replace("},", "},\n ")
        self.dprint(f"[FINAL OUTPUT]: {output}", color="bright-green")

        # PARSE ERRORS
        self.dprint(f"[PARSE ERRORS]: {self.parse_errors}", color="bright-yellow")

        # SAVE DEBUGGER OUTPUT
        self.debugger.close_log()
