import 'package:flutter/material.dart';
import '../services/family_service.dart';
import '../models/family/family_member.dart';
import '../models/family/family_invitation.dart';

class FamilyProvider with ChangeNotifier {
  final FamilyService _service = FamilyService();

  List<FamilyMember> _members = [];
  List<FamilyInvitation> _invitations = [];
  bool _isLoading = false;
  String? _error;

  List<FamilyMember> get members => _members;
  List<FamilyInvitation> get invitations => _invitations;
  bool get isLoading => _isLoading;
  String? get error => _error;

  // Load members and invitations
  Future<void> loadFamilyData() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final results = await Future.wait([
        _service.getFamilyMembers(),
        _service.getInvitations(),
      ]);
      _members = results[0] as List<FamilyMember>;
      _invitations = results[1] as List<FamilyInvitation>;
    } catch (e) {
      _error = e.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Send invitation
  Future<bool> sendInvitation({
    required String email,
    String? name,
    required String relationship,
    required String accessLevel,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final invitation = await _service.sendInvitation(
        email: email,
        name: name,
        relationship: relationship,
        accessLevel: accessLevel,
      );
      _invitations.insert(0, invitation);
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Revoke invitation
  Future<bool> revokeInvitation(int id) async {
    _isLoading = true;
    notifyListeners();

    try {
      await _service.revokeInvitation(id);
      _invitations.removeWhere((i) => i.id == id);
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  // Remove member
  Future<bool> removeMember(int id) async {
    _isLoading = true;
    notifyListeners();

    try {
      await _service.removeFamilyMember(id);
      _members.removeWhere((m) => m.id == id);
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString();
      notifyListeners();
      return false;
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
