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

d = Debugger(2)
dprint = d.print


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
    def __init__(self, stream):
        """
        The Tokenizer class tries to mimic a state machine which takes in a stream of characters
        and emits html tokens. It begins in the data state with its read head at index 0.

        :param stream: HTML string that needs to be tokenized
        """

        # TOKEN LIST
        self.output = []

        self.stream = stream

        self.state = self.data_state
        self.reconsuming = False

        # READ HEAD
        self.index = 0
        self.next_char = self.stream[0]  # The first character in the stream to have not yet been consumed
        self.current_char = ""  # Defined as the last character to have been consumed

        # BUFFERS
        self.temp_buffer = ""
        self.return_state = None  # Used by char_ref_state as a buffer to return to the state it was invoked from
        self.token_buffer = {}  # Used as a temporary buffer while creating tokens

    ###############################################################################################
    # OPERATIONS #
    def consume(self):
        mode = '[\033[96mRECONSUMING\033[0m] -> ' if self.reconsuming else '[CONSUMING]   -> '
        dprint(f"\n|=>{mode}", end="")
        if self.index < len(self.stream):
            if not self.reconsuming:
                self.next_char = self.stream[self.index]
                if self.index == 0:
                    self.current_char = ""
                else:
                    self.current_char = self.stream[self.index - 1]
                self.index += 1
                dprint(f"[Current Character: '{self.current_char}'] AND [Next Character: '{self.next_char}']\n")
                return self.current_char, self.next_char
            else:
                self.reconsuming = False
                dprint(f"[Current Character: '{self.current_char}'] AND [Next Character: '{self.next_char}']\n")
                return self.current_char, self.next_char
        else:
            dprint(f"Current Character: '{self.stream[-1]}' | Next Character: '' >-> OUT_OF_INDEX\n")
            return self.stream[-1], ""

    def emit(self, token_dict):
        # CHECKING FOR DUPLICATE ATTRIBUTES IN TOKEN BUFFER
        try:
            attr_list = token_dict["attributes"]
            duplicate_attrs = []
            for i in range(len(attr_list)):
                attr_name = attr_list[i][0]
                if attr_name not in duplicate_attrs:
                    duplicate_attrs.append(attr_name)
                else:
                    # GENERATE duplicate-attribute parse-error
                    dprint("[PARSE ERROR]: [DUPLICATE ATTRIBUTE]",
                           debugging_mode=1, color="yellow")
                    del token_dict["attributes"][i]
        except IndexError:
            pass
        self.output.append(token_dict)

        # EMPTY TOKEN BUFFER
        self.token_buffer = {}

    def consumed_as_part_of_an_attr(self):
        # CHECKS IF THE RETURN STATE IS TO ANY ONE OF THE ATTRIBUTE STATES
        char_ref_in_attr = [
            self.attr_val_double_quote_state,
            self.attr_val_single_quote_state,
            self.attr_val_unquoted_state
        ]
        return self.return_state in char_ref_in_attr

    def flush_code_pt_consumed_as_char_ref(self):
        if self.consumed_as_part_of_an_attr():
            pass  # append current temporary buffer to current attribute's value
        else:
            self.emit({
                "token": self.temp_buffer,
                "token-type": "character"
            })

    ###############################################################################################
    # STATES #
    """
    ################ DATA STATE ################
    STATUS: INCOMPLETE
    CASES: 2
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
            dprint("[PARSE ERROR]: [UNEXPECTED NULL CHARACTER]",
                   debugging_mode=2, color="yellow")
            self.emit({
                "token": current_char,
                "token-type": "character"
            })
        # END OF FILE (EOF) ENCOUNTERED
        elif next_char == "":
            self.emit({
                "token": "",
                "token-type": "eof"
            })
        else:
            self.emit({
                "token": current_char,
                "token-type": "character"
            })
            return

    """
    ################ TAG OPEN STATE ################
    STATUS: COMPLETE
    CASES: 6
    """
    def tag_open_state(self):
        current_char, next_char = self.consume()
        # POSSIBLE <!DOCTYPE type> declaration
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
                "token": "<",
                "token-type": "tag",

                # this item only exists in tag tokens
                "tag-name": "",

                # Attributes item is a list in the below form with the last item being the current attribute
                # [[attr_name, attr_value],[attr_name, attr_value], [current_attr, current_attr_val]]
                "attributes": []
            }
            self.reconsuming = True
            self.state = self.tag_name_state
            return
        # BOGUS COMMENT BEGIN <?everything here is a comment until the closing angle bracket>
        elif next_char == "?":
            # GENERATE unexpected-question-mark-instead-of-tag-name parse-error
            dprint("[PARSE ERROR]: [UNEXPECTED QUESTION MARK INSTEAD OF TAG NAME]",
                   debugging_mode=2, color="yellow")
            self.token_buffer = {
                "token": "<",
                "token-type": "comment",
                "comment-data": ""
            }
            self.reconsuming = True
            self.state = self.bogus_comment_state
            return
        # END OF FILE (EOF) ENCOUNTERED
        elif next_char == "":
            # GENERATE eof-before-tag-name parse-error
            dprint("[PARSE ERROR]: [EOF BEFORE TAG NAME]",
                   debugging_mode=2, color="yellow")
            self.emit({
                "token": "<",
                "token-type": "less-than-sign"
            })
            self.emit({
                "token": "",
                "token-type": "eof"
            })
            return
        else:
            # GENERATE invalid-first-character-of-tag-name parse-error
            dprint("[PARSE ERROR]: [INVALID FIRSTS CHARACTER OF TAG NAME]",
                   debugging_mode=2, color="yellow")
            self.emit({
                "token": "<",
                "token-type": "less-than-sign"
            })
            self.reconsuming = True
            self.state = self.data_state
            return

    """
    ################ TAG NAME STATE ################
    STATUS: COMPLETE
    CASES: 10
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
            self.token_buffer["token"] += ">"
            self.emit(self.token_buffer)
        elif next_char in self.ascii_upper_alpha:
            self.token_buffer["token"] += next_char.lower()
            self.token_buffer["tag-name"] += next_char.lower()
        elif next_char == "\0":
            # GENERATE unexpected-null-character parse-error
            dprint("[PARSE ERROR]: [UNEXPECTED NULL CHARACTER]",
                   debugging_mode=2, color="yellow")
            self.token_buffer["tag-name"] += "\uFFFD"
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            dprint("[PARSE ERROR]: [EOF IN TAG]",
                   debugging_mode=2, color="yellow")
            self.emit({
                "token": "",
                "token-type": "eof"
            })
        else:
            self.token_buffer["token"] += next_char
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
            dprint("[PARSE ERROR]: [UNEXPECTED EQUALS SIGN BEFORE ATTRIBUTE NAME]",
                   debugging_mode=2, color="yellow")
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
            dprint("[PARSE ERROR]: [UNEXPECTED NULL CHARACTER]",
                   debugging_mode=2, color="yellow")

            # self.token_buffer["attributes"][-1][0] is the current attribute name
            self.token_buffer["attributes"][-1][0] += "\uFFFD"  # REPLACEMENT CHARACTER
            return
        # MISSING =, i.e. <element attr_name" or <element _name' or <element attr_name<
        elif next_char in ['"', "'", "<"]:
            # GENERATE unexpected-character-in-attribute-name parse-error
            dprint("[PARSE ERROR]: [UNEXPECTED CHARACTER IN ATTRIBUTE NAME]",
                   debugging_mode=2, color="yellow")
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
            self.token_buffer["token"] += ">"
            self.emit(self.token_buffer)
        else:
            self.reconsuming = True
            self.state = self.attr_val_unquoted_state
            return

    """
    ################ MARKUP DECLARATION OPEN STATE ################
    STATUS: INCOMPLETE
    CASES: 0
    """
    def markup_declaration_open_state(self):
        pass

    """
    ################ END TAG OPEN STATE ################
    STATUS: INCOMPLETE
    CASES: 0
    """
    def end_tag_open_state(self):
        pass

    """
    ################ CHARACTER REFERENCE STATE ################
    STATUS: INCOMPLETE
    CASES: 1
    """
    def char_ref_state(self):
        current_char, next_char = self.consume()
        print(f"state: Character Reference State | Current Character: {current_char} | Next Character: {next_char}")
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

                self.temp_buffer += next_char
                # Invalid identifier revert required
                if self.temp_buffer[:-1] + ";\n" not in name_table_str:
                    # Revert Possible
                    if back_track_pos is not None:
                        self.index = back_track_pos
                        self.consume()
                        self.temp_buffer = self.temp_buffer[:back_track_buffer_pos]
                        break
                    # Revert Not Possible
                    break
                # Valid identifier not reverting
                else:
                    break
        # VALID MATCH FOUND
        if self.temp_buffer[:-1] + ";\n" in name_table_str or self.temp_buffer in name_table_str:
            print(f"\033[32mVALID MATCH FOUND -> {self.temp_buffer}\033[0m")
            current_char, next_char = self.consume()
            if self.consumed_as_part_of_an_attr() and self.temp_buffer[-1] != ";"\
                    and next_char in self.ascii_alphanumeric + "=":
                self.flush_code_pt_consumed_as_char_ref()
                self.state = self.return_state
                return
            if self.temp_buffer[-1] != ";":
                # GENERATE missing-semicolon-after-character-reference parse-error
                dprint("[PARSE ERROR]: [MISSING SEMICOLON AFTER CHARACTER REFERENCE]",
                       debugging_mode=2, color="yellow")

            if self.temp_buffer[:-1] + ";\n" in name_table_str:
                self.temp_buffer = self.temp_buffer[:-1] + ";"
            self.temp_buffer = self.ampersand_table[self.temp_buffer]["characters"]
            self.flush_code_pt_consumed_as_char_ref()
            self.reconsuming = True
            self.state = self.return_state
            return
        # NO VALID MATCH EXISTS
        else:
            print(f"\033[91mNO VALID MATCH FOUND -> {self.temp_buffer}\033[0m")
            self.flush_code_pt_consumed_as_char_ref()
            self.state = self.ambiguous_ampersand_state
            return

    """
    ################ AMBIGUOUS AMPERSAND STATE ################
    STATUS: COMPLETE
    """
    def ambiguous_ampersand_state(self):
        current_char, next_char = self.consume()
        print("ambiguous", current_char, next_char)

        if next_char in self.ascii_alphanumeric:
            if self.consumed_as_part_of_an_attr():
                pass  # append current_char to current attribute's value
            else:
                self.emit({
                    "token": next_char,
                    "token-type": "character"
                })
        elif next_char == ";":
            # GENERATE unknown-named-character-reference parse-error
            dprint("[PARSE ERROR]: [UNKNOWN NAMED CHARACTER REFERENCE]",
                   debugging_mode=2, color="yellow")
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
            dprint("[PARSE ERROR]: [UNEXPECTED NULL CHARACTER]",
                   debugging_mode=2, color="yellow")

            self.token_buffer["attributes"][-1][1] += "\uFFFD"  # REPLACEMENT CHARACTER
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            dprint("[PARSE ERROR]: [EOF IN TAG]",
                   debugging_mode=2, color="yellow")

            self.emit({
                "token": "",
                "token-type": "eof"
            })
            return
        else:
            self.token_buffer["attributes"][-1][1] += next_char
            return

    """
    ################ ATTRIBUTE VALUE SINGLE QUOTE STATE ################
    STATUS: NOT STARTED BUT REFERENCED
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
            dprint("[PARSE ERROR]: [UNEXPECTED NULL CHARACTER]",
                   debugging_mode=2, color="yellow")

            self.token_buffer["attributes"][-1][1] += "\uFFFD"  # REPLACEMENT CHARACTER
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            dprint("[PARSE ERROR]: [EOF IN TAG]",
                   debugging_mode=2, color="yellow")

            self.emit({
                "token": "",
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
            self.token_buffer["token"] += ">"
            self.emit(self.token_buffer)
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            dprint("[PARSE ERROR]: [EOF IN TAG]",
                   debugging_mode=2, color="yellow")

            self.emit({
                "token": "",
                "token-type": "eof"
            })
        # same treatment as the else block except generate parse error
        elif next_char in ['"', "'", "<", "=", "`"]:
            # GENERATE unexpected-character-in-unquoted-attribute-value parse-error
            dprint("[PARSE ERROR]: [UNEXPECTED CHARACTER IN UNQUOTED ATTRIBUTE VALUE]",
                   debugging_mode=2, color="yellow")

            # append character to current attribute's value
            self.token_buffer["attributes"][-1][1] += next_char
        else:
            # append character to current attribute's value
            self.token_buffer["attributes"][-1][1] += next_char

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
            self.token_buffer["token"] += ">"
            self.emit(self.token_buffer)
            return
        elif next_char == "":
            # GENERATE eof-in-tag parse-error
            dprint("[PARSE ERROR]: [EOF IN TAG]",
                   debugging_mode=2, color="yellow")
        else:
            # GENERATE missing-whitespace-between-attributes parse-error
            dprint("[PARSE ERROR]: [MISSING WHITESPACE BETWEEN ATTRIBUTES]",
                   debugging_mode=2, color="yellow")

            self.reconsuming = True
            self.state = self.before_attr_name_state
            return

    """
    ################ AFTER ATTRIBUTE NAME STATE ################
    STATUS: COMPLETE
    """
    def after_attr_name_state(self):
        current_char, next_char = self.consume()

        if next_char == ["\t", "\r", "\n", "\f", " "]:
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
            dprint("[PARSE ERROR]: [EOF IN TAG]",
                   debugging_mode=2, color="yellow")

            self.emit({
                "token": "",
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
    STATUS: INCOMPLETE
    """
    def self_closing_start_tag_state(self):
        pass

    """
    ################ BOGUS COMMENT STATE ################
    STATUS: INCOMPLETE
    """
    def bogus_comment_state(self):
        pass

    ###############################################################################################
    # MAIN RUNTIME #
    def tokenize(self):
        while self.index < len(self.stream):
            # DEBUGGING #
            state_name = self.state.__name__.upper().replace('_', ' ')
            dprint(f"[{state_name}]: ", color="magenta", end="")
            # DEBUGGING OVER #
            self.state()
        # FINAL OUTPUT
        print(self.output)
