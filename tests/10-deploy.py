#!/usr/bin/env python

import amulet
import unittest
import re


class TestDeployment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = amulet.Deployment(series='xenial')
        cls.d.add('etcd')
        cls.d.setup(timeout=1200)
        cls.d.sentry.wait_for_messages({'etcd':
                                        re.compile('Healthy*|Unhealthy*')})
        # cls.d.sentry.wait()
        cls.etcd = cls.d.sentry['etcd']
        # find the leader
        for unit in cls.etcd:
            leader_result = unit.run('is-leader')
            if leader_result[0] == 'True':
                cls.leader = unit

    def test_leader_status(self):
        ''' Verify our leader is running the etcd daemon '''
        status = self.leader.run('service etcd status')
        self.assertTrue("running" in status[0])

    def test_node_scale(self):
        ''' Scale beyond 1 node because etcd supports peering as a standalone
        application.'''
        # Ensure we aren't testing a single node
        if not len(self.etcd) > 1:
            self.d.add_unit('etcd', timeout=1200)
            self.d.sentry.wait()

        for unit in self.etcd:
            status = unit.run('service etcd status')
            self.assertFalse(status[1] == 1)
            self.assertTrue("running" in status[0])

    def test_cluster_health(self):
        ''' Iterate all the units and verify we have a clean bill of health
        from etcd '''
        for unit in self.etcd:
            health = unit.run('etcdctl cluster-health')
            self.assertTrue('unhealthy' not in health)
            self.assertTrue('unavailable' not in health)

    def test_leader_knows_all_members(self):
        ''' Test we have the same number of units deployed and reporting in
        the etcd cluster as participating'''

        certs = "ETCDCTL_KEY_FILE=/etc/ssl/etcd/server-key.pem " \
                " ETCDCTL_CERT_FILE=/etc/ssl/etcd/server.pem" \
                " ETCDCTL_CA_FILE=/etc/ssl/etcd/ca.pem"

        # format the command, and execute on the leader
        out = self.leader.run('{} etcdctl member list'.format(certs))[0]
        # turn the output into a list so we can iterate
        members = out.split('\n')
        for item in members:
            # this is responded when TLS is enabled and we don't have proper
            # Keys. This is kind of a "ssl works test" but of the worst
            # variety... assuming the full stack completed.
            self.assertTrue('etcd cluster is unavailable' not in members)
        self.assertTrue(len(members) == len(self.etcd))


if __name__ == '__main__':
    unittest.main()
