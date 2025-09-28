from __future__ import print_function

import json
import logging
from datetime import datetime, timedelta
import rospy
from paho.mqtt.client import Client

logger = logging.getLogger(__name__)


class TestLaunchInfo:
    """
    Test launch info message sent to ULISES
    """
    def __init__(self, observation_model_name, task_id, test_id):
        self.observation_model_name = observation_model_name
        self.task_id = task_id
        self.test_id = test_id

    def as_dict(self):
        return {'ObsModelName': self.observation_model_name,
                'TaskId': self.task_id,
                'TestId': self.test_id}

    def as_json(self):
        return json.dumps(self.as_dict())


class TestLaunchAck:
    """
    Test launch ACK sent by ULISES
    """
    def __init__(self, test_id, message):
        self.test_id = test_id
        self.message = message

    @classmethod
    def from_json(cls, json_in):
        json_parsed = json.loads(json_in)
        if json_parsed['Message'] == 'ACK':
            return cls(test_id=json_parsed['TestId'], message=json_parsed['Message'])
        else:
            return None

    def as_json(self):
        return {'TestId': self.test_id, 'Message': self.message}


class TestStatusMessage:
    """
    Test Status Message sent to stop ULISES
    """
    STATUS_STOP = 'Stop'
    STATUS_START = 'Start'

    def __init__(self, test_id, status):
        self.test_id = test_id
        self.status = status

    def to_json(self):
        return json.dumps({'TestId': self.test_id})


class DiagnosisTestResult:
    """
    Test result message sent by ULISES
    """
    def __init__(self, timestamp, phase_name, situation_name, step_name, constraints, eval_result):
        self.timestamp = timestamp
        self.phase_name = phase_name
        self.situation_name = situation_name
        self.step_name = step_name
        self.constraints = constraints
        self.eval_result = eval_result

    @classmethod
    def from_json(cls, json_in):
        json_parsed = json.loads(json_in)
        return DiagnosisTestResult(timestamp=json_parsed['Timestamp'], phase_name=json_parsed['PhaseName'],
                                   situation_name=json_parsed['SituationName'], step_name=json_parsed['StepName'],
                                   constraints=json_parsed['Constraints'], eval_result=json_parsed['EvalResult'])

    def as_dict(self):
        return {'Timestamp': self.timestamp, 'PhaseName': self.phase_name, 'SituationName': self.situation_name,
                'StepName': self.step_name, 'Constraints': self.constraints, 'EvalResult': self.eval_result}

    def as_json(self):
        return json.dumps(self.as_dict())


class UlisesTestHelper:
    """
    ULISES test helper
    """
    __WAIT_INTERVAL = 1

    def __init__(self, mqtt_host='127.0.0.1', mqtt_port=1883, mqtt_user='', mqtt_password=None,
                 test_launch_info=None, assert_on_exit=False, ignore_ack=False):
        """
        Initialization for test helper
        :param mqtt_host: Host of the MQTT broker to connect to
        :param mqtt_port: Port of the MQTT broker
        :param mqtt_user: Username for the MQTT broker
        :param mqtt_password: Password for the MQTT broker
        :param test_launch_info: TestLaunchInfo object containing all the test information to be sent to ULISES
        :param assert_on_exit: Automatically perform the assertion on context exit
        :param ignore_ack: Ignore not receiving the ACK from the tool
        """
        self.test_launch_ack = None
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.control_topic = 'ULISES_test'
        self.test_info_topic = 'testInfo'
        self.result_topic = 'diagnosisResult'
        self.mqtt_client = None
        self.mqtt_thread = None
        self.test_result = None
        self.test_launch_info = test_launch_info
        self.assert_on_exit = assert_on_exit
        self.test_finished_sent = False
        self.ignore_ack = ignore_ack
        self.__initialize_mqtt__()
        if not self.test_launch_info:
            raise ValueError('No test launch info supplied')

    def __enter__(self):
        """
        This method is called on context enter. See https://realpython.com/python-with-statement/ for more info.
        :return: Self instance of the helper
        """
        self.__initialize_mqtt__()
        self.__publish_test_launch_info__()
        if not self.ignore_ack:
            self.__wait_for_ack__()
        return self

    def __initialize_mqtt__(self):
        """
        MQTT initialization method. Connects to the broker and sets the corresponding callbacks for the topics.
        """
        self.mqtt_client = Client()
        self.mqtt_client.username_pw_set(username=self.mqtt_user, password=self.mqtt_password)
        self.mqtt_client.connect(host=self.mqtt_host, port=self.mqtt_port)
        self.mqtt_client.message_callback_add(self.result_topic, self.__test_result_message_callback__)
        self.mqtt_client.message_callback_add(self.control_topic, self.__testinfo_messages_topic_callback__)
        self.mqtt_client.subscribe(self.result_topic)
        self.mqtt_client.loop_start()

    def __publish_test_launch_info__(self):
        """
        Internal method for publishing the Test Launch Info to ULISES.
        """
        self.mqtt_client.publish(self.test_info_topic, self.test_launch_info.as_json())
        rospy.loginfo('Sending test info to ulises')

    def __testinfo_messages_topic_callback__(self, client, userdata, message):
        """
        Callback for Test Info ACK messages.
        :param client: MQTTClient
        :param userdata: MQTT Userdata
        :param message: MQTT message containing a topic and a payload
        """
        try:
            launch_ack_message = TestLaunchAck.from_json(message.payload)
            if self.test_launch_info.test_id == launch_ack_message.test_id:
                self.test_launch_ack = launch_ack_message
                rospy.loginfo('Test launch ACK received')
            else:
                rospy.logwarn('Ignoring ACK message for another test id')
        except Exception:
            pass

    def __test_result_message_callback__(self, client, userdata, message):
        """
        Callback for Test Result messages.
        :param client: MQTTClient
        :param userdata: MQTT Userdata
        :param message: MQTT message containing a topic and a payload
        """
        try:
            self.test_result = DiagnosisTestResult.from_json(message.payload)
            rospy.loginfo('Test result received from tool')
        except Exception as e:
            rospy.logwarn('Unable to parse diagnosis test result, exception: %s' % e)

    def __wait_for_ack__(self, timeout=10):
        """
        Method called for waiting for ULISES ACK message.
        :param timeout: Timeout for waiting, 10s by default
        """
        start_time = datetime.now()
        while not self.test_launch_ack and not (start_time + timedelta(seconds=timeout) < datetime.now()):
            rospy.logwarn('Tool start ACK not received, waiting %d seconds' % self.__WAIT_INTERVAL)
            rospy.sleep(self.__WAIT_INTERVAL)
        if not self.test_launch_ack:
            rospy.logerr("The tool wasn't started on time")
            raise AssertionError('The tool failed to start on the specified time')

    def send_test_end_message(self):
        """
        Method for sending the test end message.
        Verifies that the message has not been sent before and sents it in that case.
        """
        if not self.test_finished_sent:
            status_message = TestStatusMessage(test_id=self.test_launch_info.test_id,
                                               status=TestStatusMessage.STATUS_STOP)
            self.mqtt_client.publish(self.control_topic, status_message.to_json())
            self.test_finished_sent = True

    def wait_assert_passed(self, timeout=30):
        """
        Method for waiting for the test result from ULISES.
        Waits for the message and raises an AssertionError in case
        that the result is not valid or if the result has not been
        received in the required time. (30s by default)
        :param timeout:
        """
        start_time = datetime.now()
        while not self.test_result and not (start_time + timedelta(seconds=timeout) < datetime.now()):
            rospy.logwarn('Feedback message not received, waiting %d seconds' % self.__WAIT_INTERVAL)
            rospy.sleep(self.__WAIT_INTERVAL)
        if not self.test_result:
            rospy.logerr('No test_result received on defined time')
            raise AssertionError('No test_result received on defined time')
        if self.test_result.eval_result is False:
            rospy.logerr('Test failed returned by tool')
            raise AssertionError('Failed returned by tool')

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit method for the context manager. See https://realpython.com/python-with-statement/ for more info.
        It closes the connection to the MQTT broker before leaving
        """
        try:
            if exc_val:
                raise exc_val
            if self.assert_on_exit:
                self.wait_assert_passed()
        except Exception as e:
            raise e
        finally:
            self.send_test_end_message()
            self.mqtt_client.disconnect()
            self.mqtt_client.loop_stop()
