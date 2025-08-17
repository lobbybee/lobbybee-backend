from django.test import TestCase
import os

class LogSetupTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # This setup runs once before all tests in this class.
        # Because of the filename (test_00_...), this test class should be
        # discovered and run by the Django test runner before other test files,
        # ensuring the log file is reset at the beginning of the test suite run.
        cls.conversation_log_path = "/home/darkwebplayer/Documents/Infywork/CRMHotel/lobbybee-backend/conversationLog.md"
        with open(cls.conversation_log_path, "w") as f:
            f.write("# Conversation Log\n\nThis document logs the conversations that occurred during testing.\n\n---\n\n")

    def test_log_file_is_created(self):
        """
        This is a placeholder test to ensure setUpClass is executed.
        It also verifies that the log file was actually created.
        """
        self.assertTrue(os.path.exists(self.conversation_log_path))
