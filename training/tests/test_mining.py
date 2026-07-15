import unittest

from training.generation import GenerationConfig
from training.mining import describe_mined_program, mine_programs


class MiningTests(unittest.TestCase):
    def test_mined_synthesis_description_contains_exact_rules(self):
        description = describe_mined_program(
            "a=b\n(end)b=", ("a", "b"), 3
        )
        self.assertIn("输入是一个仅由 `a`、`b` 组成的字符串", description)
        self.assertIn("最左侧", description)
        self.assertIn("结尾", description)
        self.assertIn("重新从规则 1 检查", description)
        self.assertNotIn("公开样例", description)

    def test_bounded_mining_is_reproducible_filtered_and_clustered(self):
        config = GenerationConfig(max_program_lines=4, max_string_length=8)
        first = mine_programs(seed=44, limit=20, config=config)
        second = mine_programs(seed=44, limit=20, config=config)
        self.assertEqual(first, second)
        self.assertEqual(20, len(first))
        self.assertTrue(all(item.source_type == "random_mined" for item in first))
        self.assertTrue(
            all("behavior_properties" in item.parameters for item in first)
        )
        self.assertTrue(all(item.description_style == "rules" for item in first))
        self.assertTrue(all("公开样例" not in item.description for item in first))
        structures = {item.program for item in first}
        self.assertEqual(20, len(structures))


if __name__ == "__main__":
    unittest.main()
