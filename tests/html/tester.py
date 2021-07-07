"""
HTML PARSER TESTS

TEST ID FORMAT: STAGE@TEST_FILE#TEST_INDEX
FOR EXAMPLE THE FIRST TEST IN ./TEST-DATA/TOKENIZER/ENTITIES.JSON WOULD BE "tokenizer@entities#1"
"""

import os
import json
from src.html.tokenizer import Tokenizer


class TestTokenizer:
    # SYMBOL MAP
    sm = {
        True: "\033[92m ✔ \033[0m",
        False: "\033[91m ❌ \033[0m",
    }

    def __init__(self, test_data_dir="./test-data/tokenizer"):
        self.test_data_dir = test_data_dir
        self.run_tests()

    def run_tests(self):
        files = [file for file in os.listdir(self.test_data_dir) if file.endswith(".json")]
        pass_count = 0  # how many tests passed
        failed_tests = []  # list of test ids which failed with which test they failed
        for file in files:
            with open(f"{self.test_data_dir}/{file}", "r") as f:
                test_list = json.load(f)

            # TEST LIST CONTAINS TEST CASES (TYPE: DICT) IN A SINGLE FILE
            for test_case in test_list:
                # CURRENTLY SKIPPING SOME TESTS
                supported_test_keys = ["description", "input", "output", "errors", "id"]
                if all(key in supported_test_keys for key in test_case.keys()):
                    try:
                        # ERRORS KEYWORD
                        if "errors" in test_case.keys():
                            errors = [err["code"] for err in test_case["errors"]]
                        else:
                            errors = []

                        # ACTUAL RESULT
                        result = Tokenizer(test_case["input"], debug_lvl=0)

                        # UPDATE PASS COUNT OR FAILED TEST BASED ON ACTUAL RESULT
                        if result.output == test_case["output"] and result.parse_errors == errors:
                            pass_count += 1
                        else:
                            # CALCULATE GRADE
                            grade = self.sm[result.output == test_case['output']] + self.sm[result.parse_errors == errors]

                            failed_tests.append(f"{test_case['id']}{grade} | {result.parse_errors} {errors}")
                    except Exception as e:
                        print(f"\033[31m[RUNTIME ERROR]: [ {test_case['id']} ]:\n",
                              e, "\033[0m\n", sep="")

        # HOW MANY TESTS PASSED
        print(f"\033[32;1m{pass_count} TESTS PASSED {self.sm[True]}")

        # HOW MANY TESTS FAILED AND WHICH TEST THEY FAILED
        print("\033[31;1;4m", "#" * 20, " FAILED TESTS ", "#" * 20, "\033[0m", sep="")
        print("\n".join(failed_tests))


if __name__ == "__main__":
    TestTokenizer()
