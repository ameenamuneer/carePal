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
        _service.getFamilyInvitations(),
      ]);

      final memberRes = results[0] as Map<String, dynamic>;
      final inviteRes = results[1] as Map<String, dynamic>;

      if (memberRes['results'] != null) {
        _members = (memberRes['results'] as List)
            .map((i) => FamilyMember.fromJson(i))
            .toList();
      }

      if (inviteRes['results'] != null) {
        _invitations = (inviteRes['results'] as List)
            .map((i) => FamilyInvitation.fromJson(i))
            .toList();
      }
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
      final data = {
        'email': email,
        'name': name,
        'relationship': relationship,
        'access_level': accessLevel,
      };

      final response = await _service.sendFamilyInvitation(data);
      final invitation = FamilyInvitation.fromJson(response);

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
      await _service.cancelFamilyInvitation(id);
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
      await _service.deleteFamilyMember(id);
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
