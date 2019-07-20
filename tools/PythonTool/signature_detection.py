import csv
import io
import pandas as pd
import InputLog
import dateutil.parser
import time
from pytz import timezone

class SignatureDetector:

    EVENT_LOGIN="4624"
    EVENT_TGT = "4768"
    EVENT_ST="4769"
    EVENT_PRIV = "4672"
    EVENT_PROCESS = "4688"
    EVENT_PRIV_SERVICE = "4673"
    EVENT_PRIV_OPE = "4674"
    EVENT_NTLM = "4776"
    EVENT_SHARE = "5140"
    SYSTEM_DIR = "c:\windows";
    SYSTEM_DIR2 = "c:\program files";
    PSEXESVC = "psexesvc";
    ADMINSHARE="\c$"
    ADMINSHARE_2 = "admin$"
    IPC = "\ipc$"
    SYSTEM="system"
    ANONYMOUS="anonymous logon"
    CMD="cmd.exe"
    RUNDLL="rundll32.exe"
    RESULT_NORMAL="normal"
    RESULT_PRIV="attack: Unexpected privilege is used"
    RESULT_CMD="attack: command on blackList is used"
    RESULT_MAL_CMD = "attack: Abnormal command or tool is used"
    RESULT_ADMINSHARE = "attack: Admin share is used"
    RESULT_NOTGT="attack: Golden Ticket is used"
    RESULT_ROMANCE = "attack: Eternal Romance is used"
    RESULT_SILVER = "attack: Silver Ticket is used"
    WARN = "warning:ST without TGT"

    df=pd.DataFrame(data=None, index=None, columns=["datetime","eventid","accountname","clientaddr","servicename","processname","objectname","sharename", "securityid"], dtype=None, copy=False)
    df_admin = pd.DataFrame(data=None, index=None, columns=[ "accountname"], dtype=None, copy=False)
    df_cmd = pd.DataFrame(data=None, index=None, columns=["processname","tactics"], dtype=None, copy=False)
    df_cmd_white = pd.DataFrame(data=None, index=None, columns=["processname"], dtype=None, copy=False)

    cnt=0

    def __init__(self):
        print("constructor called")

    def is_attack(self):
        print("is_attack called")

    @staticmethod
    def signature_detect(datetime, eventid, accountname, clientaddr, servicename, processname, objectname, sharedname, securityid):
        """ Detect attack using signature based detection.
        :param datetime: Datetime of the event
        :param eventid: EventID
        :param accountname: Accountname
        :param clientaddr: Source IP address
        :param servicename: Service name
        :param processname: Process name(command name)
        :param objectname: Object name
        :return : True(1) if attack, False(0) if normal
        """

        inputLog = InputLog.InputLog(datetime, eventid, accountname, clientaddr, servicename, processname, objectname, sharedname, securityid)
        return SignatureDetector.signature_detect(inputLog)

    @staticmethod
    def signature_detect(inputLog):
        """ Detect attack using signature based detection.
        :param inputLog: InputLog object of the event
        :return : True(1) if attack, False(0) if normal
        """
        result=SignatureDetector.RESULT_NORMAL

        if (inputLog.get_eventid() == SignatureDetector.EVENT_PROCESS):
            result = SignatureDetector.isEternalBlue(inputLog)

        elif (inputLog.get_eventid() == SignatureDetector.EVENT_SHARE):
            result = SignatureDetector.isEternalBlue(inputLog)
            if(result==SignatureDetector.RESULT_NORMAL):
                result=SignatureDetector.isEternalRomace(inputLog)
            if (result == SignatureDetector.RESULT_NORMAL):
                result = SignatureDetector.isEternalWin8(inputLog)

        elif (inputLog.get_eventid() == SignatureDetector.EVENT_LOGIN):
            result = SignatureDetector.isEternalWin8(inputLog)


        elif (inputLog.get_eventid() == SignatureDetector.EVENT_NTLM):
            result = SignatureDetector.isEternalWin8(inputLog)

        series = pd.Series([inputLog.get_datetime(),inputLog.get_eventid(),inputLog.get_accountname(),inputLog.get_clientaddr(),
                      inputLog.get_servicename(),inputLog.get_processname(),inputLog.get_objectname(), inputLog.get_sharedname(), inputLog.get_securityid()], index=SignatureDetector.df.columns)
        SignatureDetector.df=SignatureDetector.df.append(series, ignore_index = True)

        return result

    @staticmethod
    def isAdminshare(inputLog):
        if inputLog.get_sharedname().find(SignatureDetector.ADMINSHARE)>=0 or inputLog.get_sharedname().find(SignatureDetector.ADMINSHARE_2)>=0:
            return SignatureDetector.RESULT_ADMINSHARE

        return SignatureDetector.RESULT_NORMAL

    @staticmethod
    def isEternalRomace(inputLog):
        time.sleep(1)
        logs=None
        # share name is 'IPC' and account is computer account
        if (inputLog.get_sharedname().find(SignatureDetector.IPC)>=0 and inputLog.get_accountname().endswith("$")):
                # Check whether admin share with computer account is used within 2 seconds
            logs = SignatureDetector.df[SignatureDetector.df.accountname.str.endswith("$")]
            logs = logs[(SignatureDetector.df.clientaddr == inputLog.get_clientaddr())
                        & ((SignatureDetector.df.sharename.str.endswith(SignatureDetector.ADMINSHARE)
                        |SignatureDetector.df.sharename.str.endswith(SignatureDetector.ADMINSHARE_2)))]

        if (inputLog.get_sharedname().find(SignatureDetector.ADMINSHARE)>=0 or inputLog.get_sharedname().find(SignatureDetector.ADMINSHARE_2)>=0):
                # account name ends with '$'
            if (inputLog.get_accountname().endswith("$")):
                logs = SignatureDetector.df[SignatureDetector.df.accountname.str.endswith("$")]
                logs = logs[(SignatureDetector.df.clientaddr == inputLog.get_clientaddr())
                                & (SignatureDetector.df.sharename.str.endswith(SignatureDetector.IPC))]

        if ((logs is not None) and len(logs) > 0):
            now=dateutil.parser.parse(inputLog.get_datetime())
            now = timezone('UTC').localize(now)
            last_date=dateutil.parser.parse(logs.tail(1).datetime.str.cat())
            last_date = timezone('UTC').localize(last_date)
            diff=(last_date - now).total_seconds()
            if(diff<2):
                print("Signature E(EternalRomace): " + SignatureDetector.RESULT_ROMANCE)
                return SignatureDetector.RESULT_ROMANCE

        return SignatureDetector.RESULT_NORMAL

    @staticmethod
    def isEternalWin8(inputLog):
        time.sleep(1)
        logs = None
        logs_login = None
        logs_ntlm = None
        logs_share = None

        # share name is 'IPC'
        if (inputLog.get_sharedname().find(SignatureDetector.IPC) >= 0 ):
            # Check whether 4624 and 4776 events are recorded from the same account within 2 seconds
            logs = SignatureDetector.df[SignatureDetector.df.accountname == inputLog.get_accountname()]
            if ((logs is not None) and len(logs) > 0):
                logs_login = logs[(SignatureDetector.df.eventid == SignatureDetector.EVENT_LOGIN) &
                                  (SignatureDetector.df.clientaddr == inputLog.get_clientaddr()) ]
                logs_ntlm = logs[(SignatureDetector.df.eventid == SignatureDetector.EVENT_NTLM)]

            if ((logs_login is not None) and len(logs_login) > 0) and ((logs_ntlm is not None) and (len(logs_ntlm) > 0)):
                now = dateutil.parser.parse(inputLog.get_datetime())
                now = timezone('UTC').localize(now)
                last_date = dateutil.parser.parse(logs_login.tail(1).datetime.str.cat())
                last_date = timezone('UTC').localize(last_date)
                diff_login = (last_date - now).total_seconds()

                last_date = dateutil.parser.parse(logs_ntlm.tail(1).datetime.str.cat())
                last_date = timezone('UTC').localize(last_date)
                diff_ntlm = (last_date - now).total_seconds()

                if (diff_login < 2 and diff_ntlm < 2):
                    SignatureDetector.cnt=SignatureDetector.cnt+1
                    if SignatureDetector.cnt>=2:
                        print("Signature E(EternalWin8): " + SignatureDetector.RESULT_ROMANCE)
                        return SignatureDetector.RESULT_ROMANCE

        # 4624
        if (inputLog.get_eventid()==SignatureDetector.EVENT_LOGIN):
            # Check whether 5140 and 4776 events are recorded from the same account within 2 seconds
            logs = SignatureDetector.df[SignatureDetector.df.accountname == inputLog.get_accountname()]
            if ((logs is not None) and len(logs) > 0):
                logs_share = logs[(SignatureDetector.df.eventid == SignatureDetector.EVENT_SHARE) &
                                  (SignatureDetector.df.clientaddr == inputLog.get_clientaddr()) &
                                  (SignatureDetector.df.sharename.str.endswith(SignatureDetector.IPC))
                                  ]
                logs_ntlm = logs[(SignatureDetector.df.eventid == SignatureDetector.EVENT_NTLM)]

            if ((logs_share is not None) and len(logs_share) > 0) and ((logs_ntlm is not None) and (len(logs_ntlm) > 0)):
                now = dateutil.parser.parse(inputLog.get_datetime())
                now = timezone('UTC').localize(now)
                last_date = dateutil.parser.parse(logs_share.tail(1).datetime.str.cat())
                last_date = timezone('UTC').localize(last_date)
                diff_share = (last_date - now).total_seconds()

                last_date = dateutil.parser.parse(logs_ntlm.tail(1).datetime.str.cat())
                last_date = timezone('UTC').localize(last_date)
                diff_ntlm = (last_date - now).total_seconds()

                if (diff_share < 2 and diff_ntlm < 2):
                    SignatureDetector.cnt=SignatureDetector.cnt+1
                    if SignatureDetector.cnt>=2:
                        print("Signature E(EternalWin8): " + SignatureDetector.RESULT_ROMANCE)
                        return SignatureDetector.RESULT_ROMANCE

        # 4776
        if (inputLog.get_eventid()==SignatureDetector.EVENT_NTLM):
            # Check whether 5140 and 4624 events are recorded from the same account within 2 seconds
            logs = SignatureDetector.df[SignatureDetector.df.accountname == inputLog.get_accountname()]
            if ((logs is not None) and len(logs) > 0):
                logs_share = logs[(SignatureDetector.df.eventid == SignatureDetector.EVENT_SHARE) &
                (SignatureDetector.df.sharename.str.endswith(SignatureDetector.IPC))
                ]
                logs_login = logs[(SignatureDetector.df.eventid == SignatureDetector.EVENT_LOGIN)]

            if ((logs_share is not None) and len(logs_share) > 0) and ((logs_login is not None) and (len(logs_login) > 0)):
                now = dateutil.parser.parse(inputLog.get_datetime())
                now = timezone('UTC').localize(now)
                last_date = dateutil.parser.parse(logs_share.tail(1).datetime.str.cat())
                last_date = timezone('UTC').localize(last_date)
                diff_share = (last_date - now).total_seconds()

                last_date = dateutil.parser.parse(logs_login.tail(1).datetime.str.cat())
                last_date = timezone('UTC').localize(last_date)
                diff_login = (last_date - now).total_seconds()

                if (diff_share < 2 and diff_login < 2):
                    SignatureDetector.cnt = SignatureDetector.cnt + 1
                    if SignatureDetector.cnt >= 2:
                        print("Signature E(EternalWin8): " + SignatureDetector.RESULT_ROMANCE)
                        return SignatureDetector.RESULT_ROMANCE

        return SignatureDetector.RESULT_NORMAL


    @staticmethod
    def isEternalBlue(inputLog):
        time.sleep(1)
        logs=None

        # security id is system and (process name is cmd.exe or rundll32.exe)
        if (inputLog.get_securityid()==SignatureDetector.SYSTEM and
            (inputLog.get_processname().endswith(SignatureDetector.CMD)
             or inputLog.get_processname().endswith(SignatureDetector.RUNDLL))
        ):
            # Check whether ANONYMOUS IPC access is used within 2 seconds
            logs = SignatureDetector.df[((SignatureDetector.df.securityid == SignatureDetector.ANONYMOUS) | (SignatureDetector.df.accountname == SignatureDetector.ANONYMOUS))
                        & (SignatureDetector.df.sharename.str.endswith(SignatureDetector.IPC))]

        # security id is ANONYMOUS and share name is IPC security id is system and (process name is cmd.exe or rundll32) is recorded  within 2 seconds
        if ((inputLog.get_securityid() == SignatureDetector.ANONYMOUS or inputLog.get_accountname()== SignatureDetector.ANONYMOUS)
            and inputLog.get_sharedname().endswith(SignatureDetector.IPC)):
            # Check whether
            logs = SignatureDetector.df[(SignatureDetector.df.securityid == SignatureDetector.SYSTEM)
                                        & (
                                            ((SignatureDetector.df.processname.str.endswith(SignatureDetector.CMD) |
                                                (SignatureDetector.df.processname.str.endswith(SignatureDetector.RUNDLL))
                                             ))
                                        )]
        # Check whether admin share is used
        if(inputLog.get_eventid()==SignatureDetector.EVENT_SHARE and SignatureDetector.isAdminshare(inputLog)==SignatureDetector.RESULT_ADMINSHARE):
            logs = SignatureDetector.df[(SignatureDetector.df.securityid == SignatureDetector.SYSTEM)
                                        & (
                                            ((SignatureDetector.df.processname.str.endswith(SignatureDetector.CMD) |
                                                (SignatureDetector.df.processname.str.endswith(SignatureDetector.RUNDLL))
                                             ))
                                        )]

        if ((logs is not None) and len(logs) > 0):
            now = dateutil.parser.parse(inputLog.get_datetime())
            now = timezone('UTC').localize(now)
            last_date = dateutil.parser.parse(logs.tail(1).datetime.str.cat())
            last_date = timezone('UTC').localize(last_date)
            diff = (last_date -now ).total_seconds()
            if (diff <= 10):
                print("Signature E(EternalBlue): " + SignatureDetector.RESULT_ROMANCE)
                return SignatureDetector.RESULT_ROMANCE

        return SignatureDetector.RESULT_NORMAL
