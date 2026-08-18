import unittest

from evaluation.m9a_artifact_isolation import require_scientific_artifact
from evaluation.m9a_ground_truth import ContactSet, EligibleCounterpart, RawContactObservation, group_collision_events, match_dual_sided_contacts, EPSILON_CONTACT_M

def point(t, xyz, node=1): return RawContactObservation(t,node,None,xyz)
def match(t, robot_points, env):
    robot=ContactSet("ROBOT",1,tuple(point(t,p) for p in robot_points))
    sets={EligibleCounterpart(name,node,kind):ContactSet(name,node,tuple(point(t,p,node) for p in points)) for name,node,kind,points in env}
    return match_dual_sided_contacts(robot,sets)

class ContactSemanticsTests(unittest.TestCase):
    def test_matching_obstacle(self): self.assertTrue(match(1,[(0,0,0)],[('BOX',2,'obstacle',[(0,0,0)])]).validated_pair_contact)
    def test_robot_floor_only(self): self.assertFalse(match(1,[(0,0,0)],[('BOX',2,'obstacle',[])]).validated_pair_contact)
    def test_obstacle_floor_only(self): self.assertFalse(match(1,[],[('BOX',2,'obstacle',[(0,0,0)])]).validated_pair_contact)
    def test_different_positions(self): self.assertFalse(match(1,[(0,0,0)],[('BOX',2,'obstacle',[(.1,0,0)])]).validated_pair_contact)
    def test_wall(self): self.assertEqual(match(1,[(0,0,0)],[('WALL',2,'wall',[(0,0,0)])]).matched_counterpart_defs,('WALL',))
    def test_adjacent_and_separated_grouping(self):
        a=match(1,[(0,0,0)],[('BOX',2,'obstacle',[(0,0,0)])]); b=match(1.032,[(0,0,0)],[('BOX',2,'obstacle',[(0,0,0)])]); c=match(2,[(0,0,0)],[('BOX',2,'obstacle',[(0,0,0)])])
        self.assertEqual(len(group_collision_events([a,b])),1); self.assertEqual(len(group_collision_events([a,b,c])),2)
    def test_multiple_counterparts_sorted(self):
        result=match(1,[(0,0,0)],[('Z',3,'wall',[(0,0,0)]),('A',2,'obstacle',[(0,0,0)])])
        self.assertEqual(result.matched_counterpart_defs,('A','Z'))
    def test_tolerance_boundary(self): self.assertTrue(match(1,[(0,0,0)],[('BOX',2,'obstacle',[(EPSILON_CONTACT_M,0,0)])]).validated_pair_contact)
    def test_outside_tolerance(self): self.assertFalse(match(1,[(0,0,0)],[('BOX',2,'obstacle',[(EPSILON_CONTACT_M+1e-12,0,0)])]).validated_pair_contact)
    def test_fixture_rejected_by_science(self):
        with self.assertRaises(PermissionError): require_scientific_artifact({'purpose':'fixture_validation_only','split':'fixture_validation'})

if __name__=='__main__': unittest.main()
