import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/app_colors.dart';
import '../../providers/family_provider.dart';
import '../../models/family/family_member.dart';
import '../../models/family/family_invitation.dart';
import '../../widgets/loading_shimmer.dart';
import '../../widgets/error_view.dart';
import '../../widgets/empty_state.dart';
import 'invite_member_screen.dart';

class FamilyMembersScreen extends StatefulWidget {
  const FamilyMembersScreen({super.key});

  @override
  State<FamilyMembersScreen> createState() => _FamilyMembersScreenState();
}

class _FamilyMembersScreenState extends State<FamilyMembersScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<FamilyProvider>().loadFamilyData();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        backgroundColor: AppColors.surface,
        elevation: 0,
        leading: IconButton(
          icon: Icon(Icons.arrow_back, color: AppColors.textPrimary),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(
          'Family & Care Team',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColors.primary,
          unselectedLabelColor: AppColors.textSecondary,
          indicatorColor: AppColors.primary,
          indicatorWeight: 3,
          tabs: const [
            Tab(text: 'Members'),
            Tab(text: 'Invitations'),
          ],
        ),
      ),
      body: Consumer<FamilyProvider>(
        builder: (context, provider, _) {
          if (provider.isLoading && provider.members.isEmpty) {
            return _buildLoadingState();
          }

          if (provider.error != null && provider.members.isEmpty) {
            return ErrorView(
              message: provider.error!,
              onRetry: provider.loadFamilyData,
            );
          }

          return TabBarView(
            controller: _tabController,
            children: [
              _buildMembersList(provider.members),
              _buildInvitationsList(provider.invitations),
            ],
          );
        },
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(builder: (_) => const InviteMemberScreen()),
          ).then((_) {
            // Refresh data when returning from invite screen
            context.read<FamilyProvider>().loadFamilyData();
          });
        },
        backgroundColor: AppColors.primary,
        icon: const Icon(Icons.person_add),
        label: const Text('Invite'),
      ),
    );
  }

  Widget _buildLoadingState() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(20),
      child: Column(
        children: List.generate(
          3,
          (_) => Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: LoadingShimmer(height: 120, borderRadius: 20),
          ),
        ),
      ),
    );
  }

  Widget _buildMembersList(List<FamilyMember> members) {
    if (members.isEmpty) {
      return const Center(
        child: EmptyState(
          icon: Icons.people_outline,
          title: 'No Family Members Yet',
          message:
              'Invite family members or caregivers to help monitor health.',
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: context.read<FamilyProvider>().loadFamilyData,
      color: AppColors.primary,
      child: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: members.length,
        separatorBuilder: (_, __) => const SizedBox(height: 16),
        itemBuilder: (context, index) {
          final member = members[index];
          return _buildMemberCard(member);
        },
      ),
    );
  }

  Widget _buildInvitationsList(List<FamilyInvitation> invitations) {
    if (invitations.isEmpty) {
      return const Center(
        child: EmptyState(
          icon: Icons.mail_outline,
          title: 'No Pending Invitations',
          message: 'Sent invitations will appear here.',
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: context.read<FamilyProvider>().loadFamilyData,
      color: AppColors.primary,
      child: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: invitations.length,
        separatorBuilder: (_, __) => const SizedBox(height: 16),
        itemBuilder: (context, index) {
          final invitation = invitations[index];
          return _buildInvitationCard(invitation);
        },
      ),
    );
  }

  Widget _buildMemberCard(FamilyMember member) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: AppColors.shadowLight,
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: AppColors.primary.withOpacity(0.1),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Icon(Icons.person, color: AppColors.primary, size: 30),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  member.userName,
                  style: TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  member.relationship,
                  style: TextStyle(
                    fontSize: 14,
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: 8),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 4,
                  ),
                  decoration: BoxDecoration(
                    color: member.isActive
                        ? AppColors.success.withOpacity(0.1)
                        : AppColors.textTertiary.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    member.isActive ? 'Active' : 'Inactive',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: member.isActive
                          ? AppColors.success
                          : AppColors.textTertiary,
                    ),
                  ),
                ),
              ],
            ),
          ),
          PopupMenuButton<String>(
            icon: Icon(Icons.more_vert, color: AppColors.textTertiary),
            onSelected: (value) {
              if (value == 'remove') {
                _showRemoveDialog(member);
              }
            },
            itemBuilder: (BuildContext context) => <PopupMenuEntry<String>>[
              const PopupMenuItem<String>(
                value: 'remove',
                child: Text('Remove from Family'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildInvitationCard(FamilyInvitation invitation) {
    Color statusColor;
    switch (invitation.status) {
      case 'ACCEPTED':
        statusColor = AppColors.success;
        break;
      case 'DECLINED':
        statusColor = AppColors.error;
        break;
      case 'EXPIRED':
        statusColor = AppColors.textTertiary;
        break;
      default:
        statusColor = AppColors.warning;
    }

    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                invitation.inviteeEmail,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: AppColors.textPrimary,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: statusColor.withOpacity(0.1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  invitation.status,
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: statusColor,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            '${invitation.relationship} • ${invitation.accessLevel}',
            style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
          ),
          if (invitation.status == 'PENDING') ...[
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => _revokeInvitation(invitation.id),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: AppColors.error,
                      side: BorderSide(color: AppColors.error),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text('Revoke Invitation'),
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _showRemoveDialog(FamilyMember member) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Remove Family Member?'),
        content: Text(
          'Are you sure you want to remove ${member.userName}? They will lose access to your data.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppColors.error),
            child: const Text('Remove'),
          ),
        ],
      ),
    );

    if (confirm == true) {
      final success = await context.read<FamilyProvider>().removeMember(
        member.id,
      );
      if (success && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('${member.userName} removed'),
            backgroundColor: AppColors.success,
          ),
        );
      }
    }
  }

  Future<void> _revokeInvitation(int id) async {
    final success = await context.read<FamilyProvider>().revokeInvitation(id);
    if (success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Invitation revoked'),
          backgroundColor: AppColors.success,
        ),
      );
    }
  }
}
