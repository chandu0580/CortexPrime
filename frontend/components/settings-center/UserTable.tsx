"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { initialUsers, UserRecord } from "./dashboardData";
import { UserPlus, UserCheck, Shield, MoreVertical, Trash2 } from "lucide-react";
import StatusBadge, { SettingsStatusType } from "./StatusBadge";

export default function UserTable() {
  const [users, setUsers] = useState<UserRecord[]>(initialUsers);
  const [inviteName, setInviteName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<any>("Developer");
  const [showInviteForm, setShowInviteForm] = useState(false);

  const handleDeactivate = (id: string) => {
    setUsers(prev =>
      prev.map(u => {
        if (u.id === id) {
          const newStatus = u.status === "Active" ? "Deactivated" : "Active";
          return { ...u, status: newStatus };
        }
        return u;
      })
    );
  };

  const handleRemove = (id: string) => {
    setUsers(prev => prev.filter(u => u.id !== id));
  };

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteName || !inviteEmail) return;

    const newUser: UserRecord = {
      id: `usr-${Date.now()}`,
      name: inviteName,
      email: inviteEmail,
      role: inviteRole,
      status: "Active",
      lastLogin: "Never logged in",
    };

    setUsers(prev => [...prev, newUser]);
    setInviteName("");
    setInviteEmail("");
    setShowInviteForm(false);
  };

  return (
    <div className="rounded-[24px] border border-[#E5E7EB] bg-white p-6 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
      {/* Header and Invite Trigger */}
      <div className="mb-6 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h3 className="text-base font-bold text-[#111827]">
            Users & Roles Administration
          </h3>
          <p className="mt-1 text-xs font-medium text-[#6B7280]">
            Manage user authorization profiles, enterprise admin roles, and active statuses.
          </p>
        </div>

        <button
          onClick={() => setShowInviteForm(!showInviteForm)}
          className="inline-flex items-center rounded-xl bg-[#38B88A] px-3.5 py-2 text-xs font-bold text-white shadow-[0_4px_14px_rgba(56,184,138,0.25)] transition-all hover:bg-[#2F9F77] hover:shadow-[0_6px_16px_rgba(56,184,138,0.3)] active:scale-[0.98] focus:outline-none"
        >
          <UserPlus className="mr-1.5 h-3.5 w-3.5" />
          Invite User
        </button>
      </div>

      {/* Invite Form overlay banner */}
      <AnimatePresence>
        {showInviteForm && (
          <motion.form
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            onSubmit={handleInvite}
            className="mb-6 overflow-hidden rounded-xl border border-[#D6F0E5] bg-[#E8F5EE]/40 p-4"
          >
            <h4 className="text-xs font-extrabold text-[#2F9F77] uppercase tracking-wider mb-3">Invite Enterprise User</h4>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <input
                type="text"
                placeholder="Full Name"
                value={inviteName}
                required
                onChange={(e) => setInviteName(e.target.value)}
                className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-1.5 text-xs font-semibold text-[#111827] outline-none focus:border-[#38B88A]"
              />
              <input
                type="email"
                placeholder="Email Address"
                value={inviteEmail}
                required
                onChange={(e) => setInviteEmail(e.target.value)}
                className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-1.5 text-xs font-semibold text-[#111827] outline-none focus:border-[#38B88A]"
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as any)}
                className="rounded-lg border border-[#E5E7EB] bg-white px-3 py-1.5 text-xs font-bold text-[#111827] outline-none focus:border-[#38B88A]"
              >
                <option value="Enterprise Admin">Enterprise Admin</option>
                <option value="SRE Engineer">SRE Engineer</option>
                <option value="Compliance Auditor">Compliance Auditor</option>
                <option value="Developer">Developer</option>
              </select>
            </div>
            <div className="mt-4 flex justify-end gap-2 text-xs">
              <button
                type="button"
                onClick={() => setShowInviteForm(false)}
                className="rounded-lg border border-[#E5E7EB] bg-white px-3.5 py-1.5 font-bold text-[#6B7280] hover:bg-[#F9FAFB]"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="rounded-lg bg-[#38B88A] px-3.5 py-1.5 font-bold text-white hover:bg-[#2F9F77]"
              >
                Send Invite
              </button>
            </div>
          </motion.form>
        )}
      </AnimatePresence>

      {/* Users table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[#E5E7EB] pb-3 text-xs font-bold uppercase tracking-wider text-[#6B7280]">
              <th scope="col" className="py-3.5 pl-4 pr-3">User</th>
              <th scope="col" className="px-3 py-3.5">Email</th>
              <th scope="col" className="px-3 py-3.5">Role</th>
              <th scope="col" className="px-3 py-3.5 text-center">Status</th>
              <th scope="col" className="px-3 py-3.5 text-right">Last Login</th>
              <th scope="col" className="py-3.5 pl-3 pr-4 text-center">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E5E7EB] font-medium text-[#111827]">
            <AnimatePresence initial={false}>
              {users.map((user) => (
                <motion.tr
                  key={user.id}
                  layoutId={user.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0, x: -15 }}
                  className="transition-colors hover:bg-[#F8FAFC]"
                >
                  {/* User Profile */}
                  <td className="whitespace-nowrap py-4 pl-4 pr-3">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#111827]">
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[#E8F5EE] text-[#2F9F77] font-extrabold uppercase">
                        {user.name.split(" ").map(w => w[0]).join("")}
                      </div>
                      <span>{user.name}</span>
                    </div>
                  </td>

                  {/* Email */}
                  <td className="whitespace-nowrap px-3 py-4 text-xs text-[#6B7280]">
                    {user.email}
                  </td>

                  {/* Role */}
                  <td className="whitespace-nowrap px-3 py-4 text-xs font-semibold text-[#111827]">
                    <div className="flex items-center gap-1.5">
                      <Shield className="h-3.5 w-3.5 text-[#6B7280]" />
                      <span>{user.role}</span>
                    </div>
                  </td>

                  {/* Status */}
                  <td className="whitespace-nowrap px-3 py-4 text-center">
                    <StatusBadge status={user.status as SettingsStatusType}>{user.status}</StatusBadge>
                  </td>

                  {/* Last Login */}
                  <td className="whitespace-nowrap px-3 py-4 text-right text-xs text-[#6B7280]">
                    {user.lastLogin}
                  </td>

                  {/* Actions buttons */}
                  <td className="whitespace-nowrap py-4 pl-3 pr-4 text-center">
                    <div className="flex items-center justify-center gap-1.5">
                      <button
                        onClick={() => handleDeactivate(user.id)}
                        className={`rounded-lg px-2 py-1 text-[10px] font-extrabold border transition-all ${
                          user.status === "Active"
                            ? "border-amber-100 bg-amber-50/50 text-[#A16207] hover:bg-amber-100"
                            : "border-green-100 bg-green-50/50 text-[#2F9F77] hover:bg-green-100"
                        }`}
                      >
                        {user.status === "Active" ? "Deactivate" : "Activate"}
                      </button>

                      <button
                        onClick={() => handleRemove(user.id)}
                        className="rounded-lg p-1.5 text-red-600 hover:bg-red-50"
                        title="Remove user"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </td>
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>
    </div>
  );
}
