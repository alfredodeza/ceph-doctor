import logging
from ceph_medic import metadata, terminal, daemon_types
from ceph_medic import checks, __version__

logger = logging.getLogger(__name__)


class Runner(object):

    def __init__(self):
        self.passed = 0
        self.skipped = 0
        self.failed = 0
        self.total = 0
        self.errors = []
        self.total_hosts = len(metadata['nodes'].keys())

    def run(self):
        """
        Go through all the daemons, and all checks. Single entrypoint for running
        checks everywhere.
        """
        start_header()
        for daemon_type in daemon_types:
            self.run_daemons(daemon_type)
        self.total = self.failed + self.passed
        return self

    def run_daemons(self, daemon_type):
        if metadata[daemon_type]:  # we have nodes of this type to run
            nodes_header(daemon_type)

        # naive/simple reporting for now

        for host, data in metadata[daemon_type].items():
            modules = [checks.common, getattr(checks, daemon_type, None)]
            self.run_host(host, data, modules)

    def run_host(self, host, data, modules):
        terminal.loader.write(' %s' % terminal.yellow(host))
        has_error = False
        for module in modules:
            checks = collect_checks(module)
            for check in checks:
                try:
                    result = getattr(module, check)(host, data)
                except Exception as error:
                    logger.exception('check had an unhandled error: %s', check)
                    self.errors.append(error)
                if result:
                    self.failed += 1
                    if not has_error:
                        terminal.loader.write(' %s\n' % terminal.red(host))

                    code, message = result
                    if code.startswith('E'):
                        code = terminal.red(code)
                    elif code.startswith('W'):
                        code = terminal.yellow(code)
                    print "   %s: %s" % (code, message)
                    has_error = True
                else:
                    self.passed += 1

        if not has_error:
            terminal.loader.write(' %s\n' % terminal.green(host))


run_errors = """
While running checks, ceph-medic had unhandled errors, please look at the
configured log file and report the issue along with the traceback.
"""


def report(results):
    msg = "\n{passed}{failed}{skipped}{errors}{hosts}"

    if results.failed:
        msg = terminal.red(msg)
    else:
        msg = terminal.green(msg)

    terminal.write.raw(
        msg.format(
            passed="%s passed, " % results.passed,
            failed="%s failed, " % results.failed if results.failed else '',
            skipped="%s skipped, " % results.skipped if results.skipped else '',
            errors="%s errors, " % len(results.errors) if results.errors else '',
            hosts="on %s hosts" % results.total_hosts
        )
    )
    if results.errors:
        terminal.yellow(run_errors)


start_header_tmpl = """
{title:=^80}
Version: {version: >4}    Cluster Name: "{cluster_name}"
Total hosts: [{total_hosts}]
OSDs: {osds: >4}    MONs: {osds: >4}     Clients: {osds: >4}
MDSs: {mdss: >4}    RGWs: {osds: >4}     MGRs: {osds: >7}
"""


def start_header():
    daemon_totals = dict((daemon, 0) for daemon in daemon_types)
    total_hosts = 0
    for daemon in daemon_types:
        count = len(metadata[daemon].keys())
        total_hosts += count
        daemon_totals[daemon] = count
    terminal.write.raw(start_header_tmpl.format(
        title='  Starting remote check session  ',
        version=__version__,
        total_hosts=total_hosts,
        cluster_name=metadata['cluster_name'],
        **daemon_totals))
    terminal.write.raw('=' * 80)


def nodes_header(daemon_type):
    readable_daemons = {
        'rgws': ' rados gateways ',
        'mgrs': ' managers ',
        'mons': ' mons ',
        'osds': ' osds ',
        'clients': ' clients ',
    }

    terminal.write.bold('\n{daemon:-^30}\n'.format(
        daemon=readable_daemons.get(daemon_type, daemon_type)))


def collect_checks(module):
    checks = [i for i in dir(module) if i.startswith('check')]
    return checks
