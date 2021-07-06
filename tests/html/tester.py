"""
HTML PARSER TESTS

TEST ID FORMAT: STAGE@TEST_FILE#TEST_INDEX
FOR EXAMPLE THE FIRST TEST IN ./TEST-DATA/TOKENIZER/ENTITIES.JSON WOULD BE "tokenizer@entities#1"
"""

import os
import json
from src.html.tokenizer import Tokenizer


class Test:
    symbol_map = {
        True: "\033[92m ✔ \033[0m",
        False: "\033[91m ❌ \033[0m",
        "pass": "\033[92m PASS \033[0m",
        "fail": "\033[91m FAIL \033[0m"
    }

    def __init__(self, test_data, debug_lvl=0):
        self.test_data = test_data
        self.id = self.test_data["id"]

        try:
            self.errors = self.test_data["errors"]
        except KeyError:
            self.errors = []

        self.debug_lvl = debug_lvl
        self.actual_output, self.actual_errors = self.get_actual_output()

    def get_actual_output(self):
        tokenizer = Tokenizer(stream=self.test_data["input"], debug_lvl=self.debug_lvl)
        return tokenizer.output, tokenizer.parse_errors

    def get_grade(self):
        grade = [
            False if self.actual_output != self.test_data["output"] else True,
            False if self.actual_errors != self.errors else True
        ]
        return grade

    def passed_all(self):
        grade = self.get_grade()
        return True if grade[0] and grade[1] else False

    def generate_report(self):
        grade = self.get_grade()
        report = f"""
{"#" * 30} RESULT {"#" * 30} 
[DESCRIPTION]: [ {self.test_data["description"].lower().replace(" ", "-")} ]
[STATUS]: [{self.symbol_map["pass"] if self.passed_all() else self.symbol_map["fail"]}]
[ID]: [ {self.id} ]
\033[32m[INPUT]\033[0m => \033[32m{self.test_data["input"]}\033[0m
{self.symbol_map[grade[0]]}
\033[93m[EXPECTED OUTPUT]\033[0m => \033[92m{self.test_data["output"]}\033[0m
\033[34m[ACTUAL   OUTPUT]\033[0m => \033[34m{self.actual_output}\033[0m
{self.symbol_map[grade[1]]}
\033[93m[EXPECTED ERRORS]\033[0m => \033[92m{self.errors}\033[0m
\033[34m[ACTUAL   ERRORS]\033[0m => \033[34m{self.actual_errors}\033[0m"""
        return report

    def __str__(self):
        return self.generate_report()

    def __repr__(self):
        return self.generate_report()


class TestTokenizer:
    pass_display_width = 5

    def __init__(self, test_data_dir="./test-data/tokenizer"):
        self.test_data_dir = test_data_dir
        self.run_tests()

    def run_tests(self):
        files = [file for file in os.listdir(self.test_data_dir) if file.endswith(".json")]
        failed_tests = []
        for file in files:
            with open(f"{self.test_data_dir}/{file}", "r") as f:
                test_list = json.load(f)

            for test_case in test_list:
                result = Test(test_case)

                if result.passed_all():
                    print(f"{result.id}:\033[92m ✔ \033[0m")
                else:
                    failed_tests.append(result.id)
        print("###### FAILED TESTS ######")
        print("\n".join(failed_tests))


TestTokenizer()
