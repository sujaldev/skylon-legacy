"""
THE TOKENIZER IS SUPPOSED TO CONVERT A STREAM OF HTML INTO A GROUP OF HTML TOKENS.

SINCE HTML PARSERS ARE BUILT TO FORGIVE ALL SORTS OF ERRORS, HTML'S GRAMMAR CANNOT
BE DEFINED WITH REGULAR EXPRESSIONS. TO PARSE HTML ONE CAN PICTURE A STATE MACHINE
READING A STREAM OF HTML CHARACTER BY CHARACTER (POSSIBLY MORE IN SOME STATES)
WHERE EACH CHARACTER CAN BE THOUGH OF AS AN EVENT WHICH CAN CAUSE A TRANSITION TO
ANOTHER STATE WHERE EACH STATE CAN HAVE EFFECTS LIKE TRANSITIONING TO ANOTHER STATE,
EMITTING AN HTML TOKEN, ETC.
"""
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

    ###############################################################################################
    # OPERATIONS #
    def consume(self):
        print(f"consume({'reconsuming' if self.reconsuming else ''}) -> ", end="")
        if self.index < len(self.stream):
            if not self.reconsuming:
                self.next_char = self.stream[self.index]
                if self.index == 0:
                    self.current_char = ""
                else:
                    self.current_char = self.stream[self.index - 1]
                self.index += 1
                print(f"Current Character: '{self.current_char}' | Next Character: '{self.next_char}'")
                return self.current_char, self.next_char
            else:
                self.reconsuming = False
                print(f"Current Character: '{self.current_char}' | Next Character: '{self.next_char}'")
                return self.current_char, self.next_char
        else:
            print(f"Current Character: '{self.stream[-1]}' | Next Character: '' >-> OUT_OF_INDEX")
            return self.stream[-1], ""

    def emit(self, token, token_type):
        self.output.append((token, token_type))

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
            self.emit(self.temp_buffer, "character")

    ###############################################################################################
    # STATES #
    """
    ################ DATA STATE ################
    STATUS: INCOMPLETE
    CASES: 1
    """
    def data_state(self):
        current_char, next_char = self.consume()

        print(f"state: Data State | Current Character: {current_char} | Next Character: {next_char}")
        if next_char == "&":
            self.return_state = self.data_state
            self.state = self.char_ref_state
            return
        else:
            # self.state = self.attr_val_single_quote_state
            return
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
        # possible match in named character reference table
        back_track_pos = None  # If at last invalid identifier is found revert back to the last successful match index
        back_track_buffer_pos = None  # Back track position in self.temp_buffer
        while self.index < len(self.stream):
            current_char, next_char = self.consume()

            # Possibly successful incomplete match
            if next_char in self.ascii_alphanumeric and self.index != len(self.stream):
                self.temp_buffer += next_char
                # Successful match
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
                pass  # generate missing-semicolon-after-character-reference parse-error

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
                self.emit(next_char, "character")
        elif next_char == ";":
            # Generate unknown-named-character-reference parse-error
            self.reconsuming = True
            self.state = self.return_state
        else:
            self.reconsuming = True
            self.state = self.return_state

    """
    ################ ATTRIBUTE VALUE DOUBLE QUOTE STATE ################
    STATUS: NOT STARTED BUT REFERENCED
    """
    def attr_val_double_quote_state(self):
        self.consume()
        return

    """
    ################ ATTRIBUTE VALUE SINGLE QUOTE STATE ################
    STATUS: NOT STARTED BUT REFERENCED
    """
    def attr_val_single_quote_state(self):
        self.consume()
        return

    """
    ################ ATTRIBUTE VALUE UNQUOTED STATE ################
    STATUS: NOT STARTED BUT REFERENCED
    """
    def attr_val_unquoted_state(self):
        self.consume()
        return

    ###############################################################################################
    # MAIN RUNTIME #
    def tokenize(self):
        while self.index < len(self.stream):
            self.state()
        print(self.output)
