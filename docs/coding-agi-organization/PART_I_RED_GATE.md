# Part I RED Gate

The Part-I foundation is developed test-first. The first hosted pull-request run is expected to fail because the contract tests exist before the `cogcoder.organization` implementation. That failure is intentional evidence that the tests are capable of detecting the absent foundation.

The same tests must later pass on Python 3.11 and Python 3.13 without weakening their assertions. A green run obtained by deleting or bypassing contract tests is not acceptable evidence.
