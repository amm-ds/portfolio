import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import tsParser from "@typescript-eslint/parser";

export default [
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "jsx-a11y": jsxA11y, "react-hooks": reactHooks },
    linterOptions: {
      // Files owned by other workstreams carry eslint-disable directives for
      // rules this minimal config doesn't enable yet; don't warn about them.
      reportUnusedDisableDirectives: "off",
    },
    rules: {
      ...jsxA11y.configs.recommended.rules,
      // Only the plugin's rule *definitions* are loaded here — the codebase's
      // eslint-disable react-hooks/exhaustive-deps comments need the rule to
      // exist; rule severity stays off until a later wave makes lint blocking.
      "react-hooks/exhaustive-deps": "off",
    },
  },
  { ignores: ["dist/**", "coverage/**"] },
];

