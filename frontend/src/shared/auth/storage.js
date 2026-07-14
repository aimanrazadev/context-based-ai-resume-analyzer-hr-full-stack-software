const USER_KEY = "user";

export function getStoredUser() {
  try {
    const value = localStorage.getItem(USER_KEY);
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
}

export function saveStoredUser(user) {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearStoredUser() {
  localStorage.removeItem(USER_KEY);
}

export function getStoredToken() {
  return getStoredUser()?.token || null;
}

export function getStoredRole() {
  const user = getStoredUser();
  return user?.role || user?.userType || null;
}
