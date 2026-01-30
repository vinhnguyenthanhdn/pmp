import React, { useEffect, useState } from 'react';
import { getAllUsers, updateUserStatus } from '../lib/user-service';
import type { UserProfile } from '../lib/user-service';
import '../styles/AdminPage.css';

interface AdminPageProps {
    onBack?: () => void;
}

export const AdminPage: React.FC<AdminPageProps> = ({ onBack }) => {
    const [users, setUsers] = useState<UserProfile[]>([]);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState<string | null>(null);

    const loadUsers = async () => {
        setLoading(true);
        const data = await getAllUsers();
        setUsers(data);
        setLoading(false);
    };

    useEffect(() => {
        loadUsers();
    }, []);

    const handleToggleStatus = async (user: UserProfile) => {
        if (!user.is_approved) {
            if (!confirm(`Are you sure you want to approve access for ${user.email}?`)) {
                return;
            }
        }

        setActionLoading(user.id);
        const newStatus = !user.is_approved;
        const success = await updateUserStatus(user.id, newStatus);

        if (success) {
            setUsers(users.map(u =>
                u.id === user.id ? { ...u, is_approved: newStatus } : u
            ));
        }
        setActionLoading(null);
    };


    if (loading) {
        return <div className="loading-container">Loading users...</div>;
    }

    return (
        <div className="admin-container">
            <div className="admin-header">
                <h1 className="admin-title">User Management</h1>
                {onBack && (
                    <div style={{ display: 'none' }}></div>
                )}
            </div>

            <div className="admin-stats">
                <div className="stat-card">
                    <div className="stat-value">{users.length}</div>
                    <div className="stat-label">Total Users</div>
                </div>
                <div className="stat-card">
                    <div className="stat-value">
                        {users.filter(u => !u.is_approved).length}
                    </div>
                    <div className="stat-label">Pending Approval</div>
                </div>
            </div>

            <div className="users-table-container">
                <table className="users-table">
                    <thead>
                        <tr>
                            <th>Email</th>
                            <th>Role</th>
                            <th>Status</th>
                            <th>Joined</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users.map(user => (
                            <tr key={user.id}>
                                <td>{user.email}</td>
                                <td>
                                    <span className={`role-badge ${user.role}`}>
                                        {user.role}
                                    </span>
                                </td>
                                <td>
                                    <span className={`status-badge ${user.is_approved ? 'approved' : 'pending'}`}>
                                        {user.is_approved ? 'Approved' : 'Pending'}
                                    </span>
                                </td>
                                <td>
                                    {new Date(user.created_at || '').toLocaleDateString()}
                                </td>
                                <td>
                                    <button
                                        className={`action-btn ${user.is_approved ? 'btn-revoke' : 'btn-approve'}`}
                                        onClick={() => handleToggleStatus(user)}
                                        disabled={actionLoading === user.id}
                                    >
                                        {user.is_approved ? 'Revoke' : 'Approve'}
                                    </button>

                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
};
