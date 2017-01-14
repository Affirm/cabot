from cabot.cabotapp.models import StatusCheck, StatusCheckResult

import subprocess


class ICMPStatusCheck(StatusCheck):

    class Meta(StatusCheck.Meta):
        proxy = True
        verbose_name = "icmpstatuscheck"

    @property
    def check_category(self):
        return "ICMP/Ping Check"

    def _run(self):
        result = StatusCheckResult(check=self)
        instances = self.instance_set.all()
        target = self.instance_set.get().address

        # We need to read both STDOUT and STDERR because ping can write to both, depending on the kind of error. Thanks a lot, ping.
        ping_process = subprocess.Popen("ping -c 1 " + target, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
        response = ping_process.wait()

        if response == 0:
            result.succeeded = True
        else:
            output = ping_process.stdout.read()
            result.succeeded = False
            result.error = output

        return result
