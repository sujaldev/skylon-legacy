"""
THE TOKENIZER IS SUPPOSED TO CONVERT A STREAM OF HTML INTO A GROUP OF HTML TOKENS.

SINCE HTML PARSERS ARE BUILT TO FORGIVE ALL SORTS OF ERRORS, HTML'S GRAMMAR CANNOT
BE DEFINED WITH REGULAR EXPRESSIONS. TO PARSE HTML ONE CAN PICTURE A STATE MACHINE
READING A STREAM OF HTML CHARACTER BY CHARACTER (POSSIBLY MORE IN SOME STATES)
WHERE EACH CHARACTER CAN BE THOUGHT OF AS AN EVENT WHICH CAN CAUSE A TRANSITION TO
ANOTHER STATE WHERE EACH STATE CAN HAVE EFFECTS LIKE TRANSITIONING TO ANOTHER STATE,
EMITTING AN HTML TOKEN, ETC.
"""
from lib.debugger import Debugger
import json

AMPERSAND_ENTITIES_PATH = f"{'/'.join(__file__.split('/')[:-1])}/ampersand-entities.json"


class Tokenizer:
    # CONSTANTS DEFINED IN THE SPECIFICATIONS
    ascii_digit = "0123456789"
    ascii_upper_alpha = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    ascii_lower_alpha = "abcdefghijklmnopqrstuvwxyz"
    ascii_alpha = ascii_lower_alpha + ascii_upper_alpha
    ascii_alphanumeric = ascii_alpha + ascii_digit

    # NAMED CHARACTER REFERENCE TABLE
    with open(AMPERSAND_ENTITIES_PATH, "r") as table:
        ampersand_table = json.load(table)

    ###############################################################################################
    def __init__(self, stream, debug_lvl=0, save_debug=False):
        """
        The Tokenizer class tries to mimic a state machine which takes in a stream of characters
        and emits html tokens. It begins in the data state with its read head at index 0.

        :param stream: HTML string that needs to be tokenized
        """

        # INPUT
        self.stream = stream

        # OUTPUTS
        self.output = []
        self.parse_errors = []

        # STATE MACHINE'S CURRENT STATE
        self.state = self.data_state

        # STATE MACHINE FLAGS
        self.reconsuming = False

        # READ HEAD
        self.index = 0
        self.next_char = self.stream[0]  # The first character in the stream to have not yet been consumed
        self.current_char = ""  # Defined as the last character to have been consumed

        # BUFFERS
        self.temp_buffer = ""
        self.return_state = None  # Used by char_ref_state as a buffer to return to the state it was invoked from
        self.token_buffer = {}  # Used as a temporary buffer while creating tokens

        # DEBUGGER
        self.debug_lvl = debug_lvl
        self.save_debug = save_debug
        self.debugger = Debugger(self.debug_lvl, self.save_debug)
        self.dprint = self.debugger.print

        # INITIATE TOKENIZING PROCESS
        self.tokenize()

    ###############################################################################################
    # OPERATIONS #
    def consume(self):
        mode = '[\033[96mRECONSUMING\033[0m] -> ' if self.reconsuming else '[CONSUMING]   -> '
        self.dprint(f"\n|=>{mode}", end="")
        if self.index < len(self.stream):
            if not self.reconsuming:
                self.next_char = self.stream[self.index]
                if self.index == 0:
                    self.current_char = ""
                else:
                    self.current_char = self.stream[self.index - 1]
                self.index += 1
                self.dprint(f"[Current Character: '{self.current_char}'] AND [Next Character: '{self.next_char}']\n")
                return self.current_char, self.next_char
            else:
                self.reconsuming = False
                self.dprint(f"[Current Character: '{self.current_char}'] AND [Next Character: '{self.next_char}']\n")
                return self.current_char, self.next_char
        else:
            self.dprint(f"Current Character: '{self.stream[-1]}' | Next Character: ''")
            self.dprint("|=>[OUT OF INDEX]-->", color="bright-green", end="")
            self.dprint("[❌]", color="bright-red")
            return self.stream[-1], ""

    def emit(self, token_dict):
        # CHECKING FOR DUPLICATE ATTRIBUTES IN TOKEN BUFFER AND REMOVE IF IT EXISTS
        if token_dict["token-type"] in ["start-tag", "end-tag"]:
            attr_list = token_dict["attributes"]
            duplicate_attrs = []
            for i in range(len(attr_list)):
                attr_name = attr_list[i][0]
                if attr_name not in duplicate_attrs:
                    duplicate_attrs.append(attr_name)
                else:
                    # GENERATE duplicate-attribute parse-error
                    self.generate_parse_error("DUPLICATE ATTRIBUTE")
                    del token_dict["attributes"][i]
        elif token_dict["token-type"] == "eof":
            print(self.token_buffer, self.temp_buffer)
        self.output.append(token_dict)

        # EMPTY TOKEN BUFFER
        self.token_buffer = {}

    def flush_code_pt_consumed_as_char_ref(self):
        if self.consumed_as_part_of_an_attr():
            # i.e. if buffer has valid named character then replace with its value in ampersand table
            if self.temp_buffer in self.ampersand_table.keys():
                pass
                # TODO: TEMPORARILY DISABLED CONVERSION TO ACTUAL NAMED CHARACTER FOR TESTING PURPOSES
                # self.temp_buffer = self.ampersand_table[self.temp_buffer]["characters"]
            elif self.temp_buffer[:-1] + ";" in self.ampersand_table.keys():
                valid_ligature = self.temp_buffer[:-1] + ";"
                # TODO: TEMPORARILY DISABLED CONVERSION TO ACTUAL NAMED CHARACTER FOR TESTING PURPOSES
                # self.temp_buffer = self.ampersand_table[valid_ligature]["characters"] + self.temp_buffer[-1]

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
        elif next_char in self.ascii_alpha:
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
            self.generate_parse_error("INVALID FIRSTS CHARACTER OF TAG NAME")
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
            self.state = self.before_attr_name_state
            return
        # SELF CLOSING TAG <br/>
        elif next_char == "/":
            self.state = self.self_closing_start_tag_state
            return
        elif next_char == ">":
            self.state = self.data_state
            self.emit(self.token_buffer)
        elif next_char in self.ascii_upper_alpha:
            self.token_buffer["tag-name"] += next_char.lower()
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            self.generate_parse_error("UNEXPECTED NULL CHARACTER")
            self.token_buffer["tag-name"] += "\uFFFD"
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")
            self.emit({
                "token-type": "eof"
            })
        else:
            self.token_buffer["tag-name"] += next_char

    """
    ################ BEFORE ATTRIBUTE NAME STATE ################
    STATUS: COMPLETE
    CASES: 4
    """
    def before_attr_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\r", "\n", "\f", " "]:
            return  # ignore
        elif next_char in ["/", ">", ""]:
            self.reconsuming = True
            self.state = self.after_attr_name_state
        elif next_char == "=":
            # GENERATE unexpected-equals-sign-before-attribute-name parse-error
            self.generate_parse_error("UNEXPECTED EQUALS SIGN BEFORE ATTRIBUTE NAME")
            self.token_buffer["attributes"].append([current_char, ""])
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
    CASES: 6
    """
    def attr_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\r", "\n", "\f", " ", "/", ">", ""]:
            self.reconsuming = True
            self.state = self.after_attr_name_state
            return
        elif next_char == "=":
            self.state = self.before_attr_val_state
            return
        elif next_char in self.ascii_upper_alpha:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
            return  # i.e. ignore these characters
        elif next_char == '"':
            self.state = self.attr_val_double_quote_state
            return
        elif next_char == "'":
            self.state = self.attr_val_single_quote_state
            return
        elif next_char == ">":
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
        elif self.stream[i:i+7] == "DOCTYPE":
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
            self.generate_parse_error("INCORRECTLY OPENED COMMENT]")

            self.token_buffer = {
                "token-type": "comment",
                "data": ""
            }

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
            self.generate_parse_error("ABRUPT CLOSING OF EMPTY COMMENT]")
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        else:
            self.reconsuming = True
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
            self.generate_parse_error("ABRUPT CLOSING OF EMPTY COMMENT]")
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        # <!-- COMMENT
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            self.generate_parse_error("EOF IN TAG")

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
        if next_char == ">":
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

        if next_char in [">", ""]:
            self.reconsuming = True
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
            return  # i.e. ignore these characters
        elif next_char in self.ascii_upper_alpha:
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
                "name": "\uFFFD",
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
                "force-quirks": True
            }

            self.state = self.doctype_name_state
            return

    """
    ################ DOCTYPE NAME STATE ################
    STATUS: COMPLETE
    """
    def doctype_name_state(self):
        current_char, next_char = self.consume()

        if next_char in ["\t", "\r", "\n", "\f", " "]:
            self.state = self.after_doctype_name_state
            return
        elif next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
            return
        elif next_char in self.ascii_upper_alpha:
            self.token_buffer["name"] += next_char.lower()
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
            self.token_buffer["name"] += next_char
            return

    """
    ################ AFTER DOCTYPE NAME STATE ################
    STATUS: COMPLETE
    """
    def after_doctype_name_state(self):
        i = self.index
        current_char, next_char = self.consume()

        if next_char in ["\t", "\r", "\n", "\f", " "]:
            return  # i.e. ignore these characters
        elif next_char == ">":
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
            if self.stream[i:i+6] == "PUBLIC":
                self.index += 5  # compensating for skipping PUBLIC consumption char by char
                self.state = self.after_doctype_public_keyword_state
                return
            elif self.stream[i:i+6] == "SYSTEM":
                self.index += 5  # compensating for skipping SYSTEM consumption char by char
                self.state = self.after_doctype_system_keyword_state
                return
            else:
                # GENERATE invalid-character-sequence-after-doctype-name parse-error
                self.generate_parse_error("INVALID CHARACTER SEQUENCE AFTER DOCTYPE NAME]")
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
            return  # i.e. ignore the character
        elif next_char == ">":
            self.emit(self.token_buffer)
            self.state = self.data_state
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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
                "token-type": ""
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

        if next_char in self.ascii_alpha:
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
        if next_char in self.ascii_alphanumeric:
            self.state = self.named_char_ref_state
            self.reconsuming = True

    """
    ################ NAMED CHARACTER REFERENCE STATE ################
    STATUS: COMPLETE
    """
    def named_char_ref_state(self):
        name_table_str = "\n".join(self.ampersand_table.keys())  # name section of ampersand table
        back_track_pos = None  # If at last invalid identifier is found revert back to the last successful match index
        back_track_buffer_pos = None  # Back track position/index for the Temporary buffer
        while self.index < len(self.stream):
            current_char, next_char = self.consume()

            # Possibly successful incomplete match in named reference table
            if next_char in self.ascii_alphanumeric and self.index != len(self.stream):
                self.temp_buffer += next_char
                # Update back_track positions only if successful match
                if self.temp_buffer + "\n" in name_table_str:
                    back_track_pos = self.index - 1
                    back_track_buffer_pos = len(self.temp_buffer)
            # Revert to last successful match if possible and required or break when at last the identifier is invalid
            else:
                if next_char != ";":
                    self.reconsuming = True

                self.temp_buffer += next_char
                # Invalid identifier revert required
                if self.temp_buffer[:-1] + ";\n" not in name_table_str:
                    # Revert Possible
                    if back_track_pos is not None:
                        self.index = back_track_pos
                        self.temp_buffer = self.temp_buffer[:back_track_buffer_pos]
                        break
                    # Revert Not Possible
                    break
                # Valid identifier not reverting
                else:
                    break
        # VALID MATCH FOUND
        if self.temp_buffer[:-1] + ";\n" in name_table_str or self.temp_buffer in name_table_str:
            self.dprint(f"|=>[VALID NAMED CHARACTER FOUND] -> [{self.temp_buffer}]", debugging_mode=3, color="green")
            current_char, next_char = self.consume()
            if self.consumed_as_part_of_an_attr() and self.temp_buffer[-1] != ";"\
                    and next_char in self.ascii_alphanumeric + "=":
                self.flush_code_pt_consumed_as_char_ref()
                self.state = self.return_state
                return
            if self.temp_buffer[-1] != ";":
                # GENERATE missing-semicolon-after-character-reference parse-error
                self.generate_parse_error("MISSING SEMICOLON AFTER CHARACTER REFERENCE]")

            self.temp_buffer = self.temp_buffer[:-1] + ";"
            # TODO: TEMPORARILY DISABLED CONVERSION TO ACTUAL NAMED CHARACTER FOR TESTING PURPOSES
            # self.temp_buffer = self.ampersand_table[self.temp_buffer]["characters"]
            self.flush_code_pt_consumed_as_char_ref()
            self.reconsuming = True
            self.state = self.return_state
            return
        # NO VALID MATCH EXISTS
        else:
            self.dprint(f"|=>[NO VALID NAMED CHARACTER FOUND] -> [{self.temp_buffer}]", debugging_mode=3, color="red")
            self.flush_code_pt_consumed_as_char_ref()
            self.state = self.ambiguous_ampersand_state
            return

    """
    ################ AMBIGUOUS AMPERSAND STATE ################
    STATUS: COMPLETE
    """
    def ambiguous_ampersand_state(self):
        current_char, next_char = self.consume()

        if next_char in self.ascii_alphanumeric:
            if self.consumed_as_part_of_an_attr():
                pass  # append current_char to current attribute's value
            else:
                self.emit({
                    "token-type": "character",
                    "data": next_char
                })
        elif next_char == ";":
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
        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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

        if next_char in ["\t", "\r", "\n", "\f", " "]:
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
        try:
            while self.index < len(self.stream):
                # DEBUGGING #
                state_name = self.state.__name__.upper().replace('_', ' ')
                self.dprint(f"[{state_name}]: ", color="magenta", end="")
                # DEBUGGING OVER #
                self.state()

            # IF EOF REACHED AND TOKEN BUFFER IS STILL NOT EMPTY EMIT TOKEN BUFFER TO OUTPUT
            if self.token_buffer:
                self.emit(self.token_buffer)

            # FINAL OUTPUT
            output = str(self.output).encode("utf8").decode("utf8").replace("},", "},\n ")
            self.dprint(f"[FINAL OUTPUT]: {output}", color="bright-green")

            # PARSE ERRORS
            self.dprint(f"[PARSE ERRORS]: {self.parse_errors}", color="bright-yellow")

            # SAVE DEBUGGER OUTPUT
            self.debugger.close()
        except KeyboardInterrupt:
            self.debugger.close()
            return
