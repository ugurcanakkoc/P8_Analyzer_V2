"""
Unit tests for gui/circuit_logic.py - Connection detection and network merging.

Tests the UnionFind data structure and the forked path handling algorithm.
"""

import pytest
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import List, Dict


# Mock the Point class for testing
@dataclass
class MockPoint:
    x: float
    y: float


@dataclass
class MockPathElement:
    index: int
    start_point: MockPoint
    end_point: MockPoint


@dataclass
class MockCircle:
    center: MockPoint
    radius: float = 3.0


@dataclass
class MockStructuralGroup:
    group_id: int
    elements: List[MockPathElement]
    circles: List[MockCircle]
    color: str = "black"


class TestUnionFind:
    """Tests for the UnionFind data structure."""

    def test_union_find_initialization(self):
        """Test UnionFind initializes correctly."""
        from p8_analyzer.circuit.connection_logic import UnionFind
        uf = UnionFind(5)

        assert len(uf.parent) == 5
        assert len(uf.rank) == 5
        # Initially, each element is its own parent
        for i in range(5):
            assert uf.find(i) == i

    def test_union_merges_sets(self):
        """Test union operation merges two sets."""
        from p8_analyzer.circuit.connection_logic import UnionFind
        uf = UnionFind(5)

        # Union 0 and 1
        result = uf.union(0, 1)
        assert result is True
        assert uf.find(0) == uf.find(1)

        # Union 2 and 3
        uf.union(2, 3)
        assert uf.find(2) == uf.find(3)

        # 0,1 and 2,3 should still be separate
        assert uf.find(0) != uf.find(2)

    def test_union_same_set_returns_false(self):
        """Test union returns False when elements already in same set."""
        from p8_analyzer.circuit.connection_logic import UnionFind
        uf = UnionFind(3)

        uf.union(0, 1)
        # Trying to union again should return False
        result = uf.union(0, 1)
        assert result is False

    def test_transitive_union(self):
        """Test transitive property: if A-B and B-C, then A-C."""
        from p8_analyzer.circuit.connection_logic import UnionFind
        uf = UnionFind(4)

        uf.union(0, 1)  # {0,1}, {2}, {3}
        uf.union(1, 2)  # {0,1,2}, {3}

        # 0, 1, 2 should all be in same set
        assert uf.find(0) == uf.find(1) == uf.find(2)
        # 3 should be separate
        assert uf.find(3) != uf.find(0)

    def test_get_groups(self):
        """Test get_groups returns correct groupings."""
        from p8_analyzer.circuit.connection_logic import UnionFind
        uf = UnionFind(5)

        uf.union(0, 1)
        uf.union(2, 3)
        uf.union(3, 4)

        groups = uf.get_groups()

        # Should have 2 groups: {0,1} and {2,3,4}
        assert len(groups) == 2

        # Find the group sizes
        group_sizes = sorted([len(members) for members in groups.values()])
        assert group_sizes == [2, 3]


class TestPointsAreClose:
    """Tests for the _points_are_close function."""

    def test_same_point_is_close(self):
        """Test identical points are close."""
        from p8_analyzer.circuit.connection_logic import _points_are_close
        p1 = MockPoint(100.0, 100.0)
        p2 = MockPoint(100.0, 100.0)

        assert _points_are_close(p1, p2, tolerance=2.0) is True

    def test_points_within_tolerance(self):
        """Test points within tolerance are close."""
        from p8_analyzer.circuit.connection_logic import _points_are_close
        p1 = MockPoint(100.0, 100.0)
        p2 = MockPoint(101.0, 101.0)  # Distance ~1.41

        assert _points_are_close(p1, p2, tolerance=2.0) is True

    def test_points_outside_tolerance(self):
        """Test points outside tolerance are not close."""
        from p8_analyzer.circuit.connection_logic import _points_are_close
        p1 = MockPoint(100.0, 100.0)
        p2 = MockPoint(105.0, 105.0)  # Distance ~7.07

        assert _points_are_close(p1, p2, tolerance=2.0) is False

    def test_points_exactly_at_tolerance(self):
        """Test points exactly at tolerance distance."""
        from p8_analyzer.circuit.connection_logic import _points_are_close
        p1 = MockPoint(0.0, 0.0)
        p2 = MockPoint(2.0, 0.0)  # Distance = 2.0

        assert _points_are_close(p1, p2, tolerance=2.0) is True


class TestMergeConnectedGroups:
    """Tests for the merge_connected_groups function."""

    def test_empty_groups(self):
        """Test with empty list of groups."""
        from p8_analyzer.circuit.connection_logic import merge_connected_groups

        result = merge_connected_groups([])
        assert result == {}

    def test_single_group(self):
        """Test with single group - no merging needed."""
        from p8_analyzer.circuit.connection_logic import merge_connected_groups

        group = MockStructuralGroup(
            group_id=1,
            elements=[
                MockPathElement(0, MockPoint(0, 0), MockPoint(100, 0))
            ],
            circles=[]
        )

        result = merge_connected_groups([group])
        assert len(result) == 1
        assert list(result.values())[0] == [0]

    def test_disconnected_groups_not_merged(self):
        """Test groups that don't share points remain separate."""
        from p8_analyzer.circuit.connection_logic import merge_connected_groups

        group1 = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(0, 0), MockPoint(50, 0))],
            circles=[]
        )
        group2 = MockStructuralGroup(
            group_id=2,
            elements=[MockPathElement(1, MockPoint(200, 200), MockPoint(250, 200))],
            circles=[]
        )

        result = merge_connected_groups([group1, group2], point_tolerance=2.0)

        # Should have 2 separate groups
        assert len(result) == 2

    def test_connected_groups_merged(self):
        """Test groups sharing a point are merged - THE FORK FIX."""
        from p8_analyzer.circuit.connection_logic import merge_connected_groups

        # Simulate a T-junction: main line and branch sharing endpoint at (100, 50)
        main_line = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(0, 50), MockPoint(100, 50))],
            circles=[]
        )
        branch_line = MockStructuralGroup(
            group_id=2,
            elements=[MockPathElement(1, MockPoint(100, 50), MockPoint(100, 150))],
            circles=[]
        )

        result = merge_connected_groups([main_line, branch_line], point_tolerance=2.0)

        # Should be merged into 1 group
        assert len(result) == 1
        members = list(result.values())[0]
        assert sorted(members) == [0, 1]

    def test_three_way_fork_merged(self):
        """Test three branches meeting at same point are all merged."""
        from p8_analyzer.circuit.connection_logic import merge_connected_groups

        # Three lines meeting at (50, 50)
        line1 = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(0, 50), MockPoint(50, 50))],
            circles=[]
        )
        line2 = MockStructuralGroup(
            group_id=2,
            elements=[MockPathElement(1, MockPoint(50, 50), MockPoint(100, 50))],
            circles=[]
        )
        line3 = MockStructuralGroup(
            group_id=3,
            elements=[MockPathElement(2, MockPoint(50, 50), MockPoint(50, 100))],
            circles=[]
        )

        result = merge_connected_groups([line1, line2, line3], point_tolerance=2.0)

        # All should be in one group
        assert len(result) == 1
        members = list(result.values())[0]
        assert sorted(members) == [0, 1, 2]

    def test_chain_merge(self):
        """Test chain of connected groups: A-B-C all become one network."""
        from p8_analyzer.circuit.connection_logic import merge_connected_groups

        # A connects to B at (100, 0), B connects to C at (200, 0)
        group_a = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(0, 0), MockPoint(100, 0))],
            circles=[]
        )
        group_b = MockStructuralGroup(
            group_id=2,
            elements=[MockPathElement(1, MockPoint(100, 0), MockPoint(200, 0))],
            circles=[]
        )
        group_c = MockStructuralGroup(
            group_id=3,
            elements=[MockPathElement(2, MockPoint(200, 0), MockPoint(300, 0))],
            circles=[]
        )

        result = merge_connected_groups([group_a, group_b, group_c], point_tolerance=2.0)

        # All should be merged
        assert len(result) == 1
        members = list(result.values())[0]
        assert sorted(members) == [0, 1, 2]

    def test_circles_considered_for_merge(self):
        """Test that circle centers are considered when finding connections."""
        from p8_analyzer.circuit.connection_logic import merge_connected_groups

        # Line ending near a circle center
        line_group = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(0, 0), MockPoint(99, 0))],
            circles=[]
        )
        circle_group = MockStructuralGroup(
            group_id=2,
            elements=[],
            circles=[MockCircle(center=MockPoint(100, 0))]
        )

        result = merge_connected_groups([line_group, circle_group], point_tolerance=2.0)

        # Should be merged (99,0) close to (100,0)
        assert len(result) == 1


class TestCheckIntersections:
    """Tests for the check_intersections function."""

    def test_empty_components(self):
        """Test with no components returns empty dict."""
        from p8_analyzer.circuit.connection_logic import check_intersections, CircuitComponent

        mock_result = Mock()
        mock_result.structural_groups = []

        result = check_intersections([], mock_result)
        assert result == {}

    def test_empty_groups(self):
        """Test with no structural groups returns empty dict."""
        from p8_analyzer.circuit.connection_logic import check_intersections, CircuitComponent

        mock_result = Mock()
        mock_result.structural_groups = []

        comp = CircuitComponent(
            id="BOX-1",
            label="Component",
            bbox={"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}
        )

        result = check_intersections([comp], mock_result)
        assert result == {}

    def test_point_inside_component_detected(self):
        """Test that wire endpoint inside component is detected."""
        from p8_analyzer.circuit.connection_logic import check_intersections, CircuitComponent

        # Component box at (0-100, 0-100)
        comp = CircuitComponent(
            id="BOX-1",
            label="Component",
            bbox={"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}
        )

        # Wire with endpoint at (50, 50) - inside box
        group = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(200, 200), MockPoint(50, 50))],
            circles=[]
        )

        mock_result = Mock()
        mock_result.structural_groups = [group]

        result = check_intersections([comp], mock_result)

        assert "NET-001" in result
        assert "BOX-1" in result["NET-001"]

    def test_forked_path_merged_connections(self):
        """
        THE KEY TEST: Forked paths should result in single network with all connections.

        Scenario: T-junction where main line goes to BOX-1, branch goes to BOX-2.
        Without merge: Two separate networks, each with one box.
        With merge: One network with both boxes.
        """
        from p8_analyzer.circuit.connection_logic import check_intersections, CircuitComponent

        # Two boxes
        box1 = CircuitComponent(
            id="BOX-1",
            label="Left Box",
            bbox={"min_x": 0, "max_x": 20, "min_y": 45, "max_y": 55}
        )
        box2 = CircuitComponent(
            id="BOX-2",
            label="Bottom Box",
            bbox={"min_x": 95, "max_x": 105, "min_y": 145, "max_y": 155}
        )

        # T-junction: main line (0,50) to (100,50), branch (100,50) to (100,150)
        # They share point (100, 50)
        main_line = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(10, 50), MockPoint(100, 50))],
            circles=[]
        )
        branch = MockStructuralGroup(
            group_id=2,
            elements=[MockPathElement(1, MockPoint(100, 50), MockPoint(100, 150))],
            circles=[]
        )

        mock_result = Mock()
        mock_result.structural_groups = [main_line, branch]

        # With merging (default)
        result = check_intersections([box1, box2], mock_result, merge_networks=True)

        # Should have ONE network containing BOTH boxes
        assert len(result) == 1
        net_id = list(result.keys())[0]
        assert "BOX-1" in result[net_id]
        assert "BOX-2" in result[net_id]

    def test_legacy_mode_no_merge(self):
        """Test that legacy mode doesn't merge forked paths."""
        from p8_analyzer.circuit.connection_logic import check_intersections, CircuitComponent

        box1 = CircuitComponent(
            id="BOX-1",
            label="Left Box",
            bbox={"min_x": 0, "max_x": 20, "min_y": 45, "max_y": 55}
        )
        box2 = CircuitComponent(
            id="BOX-2",
            label="Bottom Box",
            bbox={"min_x": 95, "max_x": 105, "min_y": 145, "max_y": 155}
        )

        main_line = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(10, 50), MockPoint(100, 50))],
            circles=[]
        )
        branch = MockStructuralGroup(
            group_id=2,
            elements=[MockPathElement(1, MockPoint(100, 50), MockPoint(100, 150))],
            circles=[]
        )

        mock_result = Mock()
        mock_result.structural_groups = [main_line, branch]

        # Without merging (legacy mode)
        result = check_intersections([box1, box2], mock_result, merge_networks=False)

        # Should have TWO separate networks
        assert len(result) == 2

    def test_no_duplicate_boxes_in_network(self):
        """Test that same box isn't added multiple times to a network."""
        from p8_analyzer.circuit.connection_logic import check_intersections, CircuitComponent

        # Large box that multiple wire points touch
        box = CircuitComponent(
            id="BIG-BOX",
            label="Big Component",
            bbox={"min_x": 0, "max_x": 200, "min_y": 0, "max_y": 200}
        )

        # Multiple connected groups all touching the box
        group1 = MockStructuralGroup(
            group_id=1,
            elements=[MockPathElement(0, MockPoint(50, 50), MockPoint(100, 100))],
            circles=[]
        )
        group2 = MockStructuralGroup(
            group_id=2,
            elements=[MockPathElement(1, MockPoint(100, 100), MockPoint(150, 150))],
            circles=[]
        )

        mock_result = Mock()
        mock_result.structural_groups = [group1, group2]

        result = check_intersections([box], mock_result, merge_networks=True)

        # Box should appear only once
        net_id = list(result.keys())[0]
        assert result[net_id].count("BIG-BOX") == 1


class TestCircuitComponent:
    """Tests for the CircuitComponent class."""

    def test_contains_point_inside(self):
        """Test point inside bounding box."""
        from p8_analyzer.circuit.connection_logic import CircuitComponent

        comp = CircuitComponent(
            id="TEST",
            label="Test",
            bbox={"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}
        )

        point = MockPoint(50, 50)
        assert comp.contains_point(point) is True

    def test_contains_point_outside(self):
        """Test point outside bounding box."""
        from p8_analyzer.circuit.connection_logic import CircuitComponent

        comp = CircuitComponent(
            id="TEST",
            label="Test",
            bbox={"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}
        )

        point = MockPoint(150, 150)
        assert comp.contains_point(point) is False

    def test_contains_point_with_tolerance(self):
        """Test point just outside box but within tolerance."""
        from p8_analyzer.circuit.connection_logic import CircuitComponent

        comp = CircuitComponent(
            id="TEST",
            label="Test",
            bbox={"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}
        )

        # Point just outside (103, 50)
        point = MockPoint(103, 50)
        assert comp.contains_point(point, tolerance=0) is False
        assert comp.contains_point(point, tolerance=5) is True

    def test_contains_point_on_edge(self):
        """Test point exactly on bounding box edge."""
        from p8_analyzer.circuit.connection_logic import CircuitComponent

        comp = CircuitComponent(
            id="TEST",
            label="Test",
            bbox={"min_x": 0, "max_x": 100, "min_y": 0, "max_y": 100}
        )

        # Point on edge
        point = MockPoint(100, 50)
        assert comp.contains_point(point) is True
