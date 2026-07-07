// @ts-check
const eslint = require('@eslint/js');
const { defineConfig } = require('eslint/config');
const tseslint = require('typescript-eslint');
const angular = require('angular-eslint');

module.exports = defineConfig([
  {
    files: ['**/*.ts'],
    extends: [
      eslint.configs.recommended,
      tseslint.configs.recommended,
      tseslint.configs.stylistic,
      angular.configs.tsRecommended,
    ],
    processor: angular.processInlineTemplates,
    rules: {
      '@angular-eslint/directive-selector': [
        'error',
        {
          type: 'attribute',
          prefix: 'app',
          style: 'camelCase',
        },
      ],
      '@angular-eslint/component-selector': [
        'error',
        {
          type: 'element',
          prefix: 'app',
          style: 'kebab-case',
        },
      ],
      // This codebase uses a leading underscore as the established convention
      // for a deliberately-unused variable/parameter (e.g. a callback param
      // required by an interface but not needed by this implementation) —
      // narrowly recognise that convention instead of flagging every one.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // Empty arrow functions are a pervasive, idiomatic pattern here for
      // "intentionally ignore this" callbacks (e.g. `.catch(() => {})` to
      // silence a promise rejection that's asserted on separately). Empty
      // named *methods*/function declarations are NOT included in this
      // allowance — those are rarer and more often a sign of accidentally
      // unimplemented logic, so they still get flagged (and are handled with
      // individually-commented inline disables where genuinely intentional).
      '@typescript-eslint/no-empty-function': ['error', { allow: ['arrowFunctions'] }],
    },
  },
  {
    files: ['**/*.html'],
    extends: [angular.configs.templateRecommended, angular.configs.templateAccessibility],
    rules: {},
  },
]);
