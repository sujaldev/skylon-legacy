# RUNS ONLY ONE TEST WITH THE PROVIDED ID
import json
from src.html.tokenizer import Tokenizer


def path_from_id(test_id):
    prefix = test_id.split("@")[0]
    test_name, test_index = test_id.split("@")[1].split("#")
    return f"test-data/{prefix}/{test_name}.json", int(test_index)


class SingleTokenizerTest:
    # SYMBOL MAP
    sm = {
        True: "\033[92m ✔ \033[0m",
        False: "\033[91m ❌ \033[0m",
    }

    def __init__(self, test_id, base_path="./"):
        self.test_id = test_id
        self.base_path = base_path

        self.path_from_id = path_from_id(self.test_id)
        self.path = f"{self.base_path}/{self.path_from_id[0]}"
        self.test_index = self.path_from_id[1]

        self.test_case = self.get_test_case()

    def get_test_case(self):
        with open(self.path, "r") as f:
            test_case = json.load(f)[self.test_index]
        return test_case

    def generate_report(self):
        # ERRORS KEYWORD
        if "errors" in self.test_case.keys():
            errors = self.test_case["errors"]
        else:
            errors = []

        # ACTUAL OUTPUT
        result = Tokenizer(self.test_case["input"], debug_lvl=0)

        # SET GRADE
        grade = self.sm[result.output == self.test_case['output']] + self.sm[result.parse_errors == errors]

        result = f"""[DESCRIPTION]: [{self.test_case["description"]}]
[INPUT]: {self.test_case["input"]}

[GRADE]: [{grade}]

[EXPECTED OUTPUT]: {self.test_case["output"]}
[ACTUAL   OUTPUT]: {result.output}

[EXPECTED ERRORS]: {errors}
[ACTUAL   ERRORS]: {result.parse_errors}"""
        return result

    def __str__(self):
        return self.generate_report()

    def __repr__(self):
        return self.generate_report()


print(SingleTokenizerTest("tokenizer@test1#1"))
