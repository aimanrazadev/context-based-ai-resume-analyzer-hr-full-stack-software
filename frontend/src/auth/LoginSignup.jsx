import { useEffect, useState } from "react";
import "./LoginSignup.css";
import { authAPI } from "../utils/api";
import { toast, handleApiError, handleApiSuccess } from "../utils/toast";

export default function LoginSignup({ onLoginSuccess }) {
  const [isLogin, setIsLogin] = useState(false);
  const [userType, setUserType] = useState("recruiter"); // "recruiter" or "candidate"
  const [formData, setFormData] = useState({
    email: "",
    name: "",
    password: "",
    confirmPassword: "",
    agreeToTerms: false,
    isAccredited: false
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendStatus, setBackendStatus] = useState("Checking...");

  useEffect(() => {
    let alive = true;
    authAPI
      .health()
      .then((d) => {
        if (!alive) return;
        setBackendStatus(d?.status || "Connected");
      })
      .catch(() => {
        if (!alive) return;
        setBackendStatus("Backend not reachable");
      });
    return () => {
      alive = false;
    };
  }, []);

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setError("");
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Validation
    if (!formData.email || !formData.password) {
      const msg = "Please fill in all required fields";
      setError(msg);
      toast.error(msg);
      setLoading(false);
      return;
    }

    if (!isLogin && !formData.name) {
      const msg = "Please enter your name";
      setError(msg);
      toast.error(msg);
      setLoading(false);
      return;
    }

    if (!isLogin && formData.password !== formData.confirmPassword) {
      const msg = "Passwords do not match";
      setError(msg);
      toast.error(msg);
      setLoading(false);
      return;
    }

    if (!isLogin && formData.password.length < 6) {
      const msg = "Password must be at least 6 characters";
      setError(msg);
      toast.error(msg);
      setLoading(false);
      return;
    }

    if (!isLogin && !formData.agreeToTerms) {
      const msg = "Please agree to the Privacy Policy & Terms and Conditions";
      setError(msg);
      toast.error(msg);
      setLoading(false);
      return;
    }

    try {
      const result = isLogin
        ? await authAPI.login({ email: formData.email, password: formData.password, role: userType })
        : await authAPI.signup({
            email: formData.email,
            password: formData.password,
            role: userType,
            name: formData.name
          });

      const token = result?.access_token;
      const role = result?.user?.role || userType;
      const id = result?.user?.id;

      const user = {
        id: id ?? Math.random().toString(36).slice(2),
        email: formData.email,
        name: formData.name || "User",
        role,
        userType: role, // backwards compatibility with older UI state
        token: token ?? null
      };

      localStorage.setItem("user", JSON.stringify(user));
      
      // Show success message
      handleApiSuccess(isLogin ? "Login successful!" : "Account created successfully!", {
        position: "bottom-right"
      });
      
      onLoginSuccess(user);
    } catch (err) {
      const msg = handleApiError(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        {/* Form Section - Full Width */}
        <div className="auth-form-container">
          <h1 className="auth-title">Get Started Now</h1>
          <p className="auth-subtitle">
            It's free to join and gain full access to thousands of exciting {userType === "recruiter" ? "hiring" : "job"} opportunities.
          </p>
          <p className="auth-subtitle" style={{ marginTop: 8 }}>
            Backend status: {backendStatus}
          </p>

          {/* User Type Selection */}
          <div className="user-type-selection">
            <label className={`user-type-option ${userType === "recruiter" ? "active" : ""}`}>
              <input
                type="radio"
                name="userType"
                value="recruiter"
                checked={userType === "recruiter"}
                onChange={(e) => setUserType(e.target.value)}
              />
              <span>I'm a Recruiter</span>
            </label>
            <label className={`user-type-option ${userType === "candidate" ? "active" : ""}`}>
              <input
                type="radio"
                name="userType"
                value="candidate"
                checked={userType === "candidate"}
                onChange={(e) => setUserType(e.target.value)}
              />
              <span>I'm a Candidate</span>
            </label>
          </div>

          <form onSubmit={handleSubmit} className="auth-form">
            {!isLogin && (
              <input
                type="text"
                placeholder="Name"
                value={formData.name}
                onChange={(e) => handleInputChange("name", e.target.value)}
                className="auth-input"
              />
            )}
            <input
              type="email"
              placeholder="Email Address"
              value={formData.email}
              onChange={(e) => handleInputChange("email", e.target.value)}
              className="auth-input"
            />
            <input
              type="password"
              placeholder="Password"
              value={formData.password}
              onChange={(e) => handleInputChange("password", e.target.value)}
              className="auth-input"
            />
            {!isLogin && (
              <input
                type="password"
                placeholder="Confirm Password"
                value={formData.confirmPassword}
                onChange={(e) => handleInputChange("confirmPassword", e.target.value)}
                className="auth-input"
              />
            )}

            {!isLogin && (
              <>
                <label className="auth-checkbox">
                  <input
                    type="checkbox"
                    checked={formData.agreeToTerms}
                    onChange={(e) => handleInputChange("agreeToTerms", e.target.checked)}
                  />
                  <span>
                    I agree to the website's{" "}
                    <a 
                      href="#" 
                      className="auth-link"
                      onClick={(e) => e.preventDefault()}
                    >
                      Privacy Policy & Terms and Conditions
                    </a>
                  </span>
                </label>
                {userType === "recruiter" && (
                  <label className="auth-checkbox">
                    <input
                      type="checkbox"
                      checked={formData.isAccredited}
                      onChange={(e) => handleInputChange("isAccredited", e.target.checked)}
                    />
                    <span>I certify that I am an accredited Recruiter.</span>
                  </label>
                )}
              </>
            )}

            {error && <div className="auth-error">{error}</div>}

            <button type="submit" className="auth-submit-btn" disabled={loading}>
              {loading ? "Processing..." : isLogin ? "Sign In" : "Sign Up"}
            </button>
          </form>

          <div className="auth-switch">
            {isLogin ? (
              <p>
                Don't have an account?{" "}
                <a 
                  href="#" 
                  onClick={(e) => { 
                    e.preventDefault(); 
                    setIsLogin(false); 
                  }} 
                  className="auth-link"
                >
                  Sign up here
                </a>
              </p>
            ) : (
              <p>
                Already have an account?{" "}
                <a 
                  href="#" 
                  onClick={(e) => { 
                    e.preventDefault(); 
                    setIsLogin(true); 
                  }} 
                  className="auth-link"
                >
                  Sign in here
                </a>
              </p>
            )}
          </div>

          <div className="auth-divider">
            <span>OR Continue With</span>
          </div>

          <div className="auth-social-login">
            <button 
              type="button"
              className="social-btn google"
              onClick={() => alert("Google login coming soon!")}
            >
              G
            </button>
            <button 
              type="button"
              className="social-btn facebook"
              onClick={() => alert("Facebook login coming soon!")}
            >
              f
            </button>
            <button 
              type="button"
              className="social-btn slack"
              onClick={() => alert("Social login coming soon!")}
            >
              #
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
