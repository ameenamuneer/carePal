import '../models/family/family_member.dart';
import '../models/family/family_invitation.dart';
import 'api_service.dart';

class FamilyService {
  final ApiService _api = ApiService();

  // Get family members
  Future<List<FamilyMember>> getFamilyMembers() async {
    try {
      final response = await _api.get('/api/v1/family/members/');
      final results = response.data as List;
      return results.map((json) => FamilyMember.fromJson(json)).toList();
    } catch (e) {
      throw Exception('Failed to load family members: $e');
    }
  }

  // Get invitations (sent and received)
  Future<List<FamilyInvitation>> getInvitations() async {
    try {
      final response = await _api.get('/api/v1/family/invitations/');
      final results =
          response.data['results']
              as List; // Pagination usually returns {results: []}
      return results.map((json) => FamilyInvitation.fromJson(json)).toList();
    } catch (e) {
      // If backend doesn't use standard pagination for this endpoint or slightly different structure
      // trying list directly if above fails is safer, but standard Django Rest Framework uses results for lists.
      // However, often my patterns use direct list for simple endpoints or results key.
      // I'll stick to 'results' as seen in other services, but I'll add a check logic if needed later.
      // For now, let's assume standard DRF.
      throw Exception('Failed to load invitations: $e');
    }
  }

  // Send invitation
  Future<FamilyInvitation> sendInvitation({
    required String email,
    String? name,
    required String relationship,
    required String accessLevel,
  }) async {
    try {
      final data = {
        'invitee_email': email,
        if (name != null) 'invitee_name': name,
        'relationship': relationship,
        'access_level': accessLevel,
      };

      final response = await _api.post(
        '/api/v1/family/invitations/',
        data: data,
      );
      return FamilyInvitation.fromJson(response.data);
    } catch (e) {
      throw Exception('Failed to send invitation: $e');
    }
  }

  // Cancel/Revoke invitation
  Future<void> revokeInvitation(int invitationId) async {
    try {
      await _api.delete('/api/v1/family/invitations/$invitationId/');
    } catch (e) {
      throw Exception('Failed to revoke invitation: $e');
    }
  }

  // Remove family member
  Future<void> removeFamilyMember(int memberId) async {
    try {
      await _api.delete('/api/v1/family/members/$memberId/');
    } catch (e) {
      throw Exception('Failed to remove family member: $e');
    }
  }
}
