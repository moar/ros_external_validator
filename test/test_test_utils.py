import threading
from time import sleep
from unittest import TestCase

from ulises_test_utils.test_utils import TestLaunchInfo, UlisesTestHelper, DiagnosisTestResult
from ulises_test_utils.test_utils import TestLaunchAck
from mock import patch


class MQTTMessage:
    def __init__(self, topic, payload):
        self.topic = topic
        self.payload = payload



class TestUtilsTest(TestCase):
    @patch('ulises_test_utils.test_utils.Client', autospec=True)
    def test_usage(self, mqtt_client):
        test_info = TestLaunchInfo(observation_model_name='', task_id='test', test_id='id')
        fake_test_result = DiagnosisTestResult(timestamp=123, phase_name='test', situation_name='test',
                                               step_name='test', constraints='test', eval_result=True)

        with UlisesTestHelper(test_launch_info=test_info, ignore_ack=True) as helper:
            helper.__test_result_message_callback__(client=None, userdata=None,
                                                    message=MQTTMessage(topic=helper.result_topic,
                                                                        payload=bytes(fake_test_result.as_json())))
            helper.wait_assert_passed()

    @patch('ulises_test_utils.test_utils.Client', autospec=True)
    def test_failed(self, mqtt_client):
        test_info = TestLaunchInfo(observation_model_name='', task_id='test', test_id='id')
        test_info_ack = TestLaunchAck(test_id='id', message='ACK')
        fake_test_result = DiagnosisTestResult(timestamp=123, phase_name='test', situation_name='test',
                                               step_name='test', constraints='test', eval_result=False)

        with self.assertRaises(AssertionError):
            with UlisesTestHelper(test_launch_info=test_info, ignore_ack=True) as helper:
                helper.__test_result_message_callback__(client=None, userdata=None,
                                                        message=MQTTMessage(topic=helper.result_topic,
                                                                            payload=bytes(fake_test_result.as_json())))
                helper.wait_assert_passed()

    @patch('ulises_test_utils.test_utils.Client', autospec=True)
    def test_failed_assert_on_exit(self, mqtt_client):
        test_info = TestLaunchInfo(observation_model_name='', task_id='test', test_id='id')
        fake_test_result = DiagnosisTestResult(timestamp=123, phase_name='test', situation_name='test',
                                               step_name='test', constraints='test', eval_result=False)

        with self.assertRaises(AssertionError):
            with UlisesTestHelper(test_launch_info=test_info, assert_on_exit=True, ignore_ack=True) as helper:
                helper.__test_result_message_callback__(client=None, userdata=None,
                                                        message=MQTTMessage(topic=helper.result_topic,
                                                                            payload=bytes(fake_test_result.as_json())))
