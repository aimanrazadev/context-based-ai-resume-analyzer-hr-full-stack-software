import "./MyProfile.css";
import { useMemo, useState, useEffect, useRef } from "react";
import { Camera } from "lucide-react";
import { TECH_SKILLS, ALL_SKILLS } from "../utils/skillsList";

export default function MyProfile() {
  const [skills, setSkills] = useState([]);
  const [experience, setExperience] = useState([
    {
      id: 1,
      title: "Software Developer",
      company: "Tech Company Inc.",
      startDate: "2022-01",
      endDate: null,
      description: "Developed and maintained web applications using React and Node.js",
      current: true,
    },
  ]);
  const [education, setEducation] = useState([
    {
      id: 1,
      degree: "Bachelor of Technology",
      institution: "University Name",
      graduationYear: "2022",
    },
  ]);

  const [skillsDropdown, setSkillsDropdown] = useState(false);
  const [showSkillsForm, setShowSkillsForm] = useState(false);
  const [expModal, setExpModal] = useState(false);
  const [eduModal, setEduModal] = useState(false);
  const [skillSearch, setSkillSearch] = useState("");
  const [socials, setSocials] = useState({
    linkedin: "",
    github: "",
  });
  const [editingSocials, setEditingSocials] = useState(false);
  const [editProfileModal, setEditProfileModal] = useState(false);
  const [profileFormData, setProfileFormData] = useState({ name: "", title: "" });
  const [profilePhoto, setProfilePhoto] = useState(null);
  const [userState, setUserState] = useState(null);
  const skillsDropdownRef = useRef(null);
  const fileInputRef = useRef(null);

  const user = useMemo(() => {
    try {
      const raw = localStorage.getItem("user");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }, [userState]);

  const initials = useMemo(() => {
    const name = user?.name || "Candidate";
    const parts = String(name).trim().split(/\s+/).filter(Boolean);
    const a = parts[0]?.[0] || "C";
    const b = parts[1]?.[0] || parts[0]?.[1] || "J";
    return (a + b).toUpperCase();
  }, [user]);

  const filteredSkills = useMemo(() => {
    if (!skillSearch.trim()) return [];
    return ALL_SKILLS.filter(
      (s) =>
        !skills.includes(s) &&
        s.toLowerCase().includes(skillSearch.toLowerCase())
    ).slice(0, 15);
  }, [skillSearch, skills]);

  const handleAddSkill = (skill) => {
    if (!skills.includes(skill)) {
      setSkills([...skills, skill]);
    }
    setSkillSearch("");
    setSkillsDropdown(false);
    setShowSkillsForm(false);
  };

  const handleRemoveSkill = (skill) => {
    setSkills(skills.filter((s) => s !== skill));
  };

  const handleAddExperience = () => {
    const newExp = {
      id: Date.now(),
      title: "",
      company: "",
      startDate: "",
      endDate: null,
      description: "",
      current: false,
    };
    setExperience([...experience, newExp]);
    setExpModal(true);
  };

  const handleUpdateExperience = (id, field, value) => {
    setExperience(
      experience.map((e) => (e.id === id ? { ...e, [field]: value } : e))
    );
  };

  const handleRemoveExperience = (id) => {
    setExperience(experience.filter((e) => e.id !== id));
  };

  const handleAddEducation = () => {
    const newEdu = {
      id: Date.now(),
      degree: "",
      institution: "",
      graduationYear: "",
    };
    setEducation([...education, newEdu]);
    setEduModal(true);
  };

  const handleUpdateEducation = (id, field, value) => {
    setEducation(
      education.map((e) => (e.id === id ? { ...e, [field]: value } : e))
    );
  };

  const handleRemoveEducation = (id) => {
    setEducation(education.filter((e) => e.id !== id));
  };

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (skillsDropdownRef.current && !skillsDropdownRef.current.contains(e.target)) {
        setSkillsDropdown(false);
        setShowSkillsForm(false);
      }
    };
    if (showSkillsForm) {
      document.addEventListener("mousedown", handleClickOutside);
      return () => document.removeEventListener("mousedown", handleClickOutside);
    }
  }, [showSkillsForm]);

  // Load user data on mount
  useEffect(() => {
    try {
      const userData = JSON.parse(localStorage.getItem("user") || "{}");
      setUserState(userData);
      
      // Load skills from localStorage
      const savedSkills = JSON.parse(localStorage.getItem("userSkills") || "[]");
      if (Array.isArray(savedSkills) && savedSkills.length > 0) {
        setSkills(savedSkills);
      }
      
      // Load profile photo from localStorage
      const savedPhoto = localStorage.getItem("profilePhoto");
      if (savedPhoto) {
        setProfilePhoto(savedPhoto);
      }
      
      // Load social links from localStorage
      const savedSocials = JSON.parse(localStorage.getItem("userSocials") || "{}");
      if (savedSocials.linkedin || savedSocials.github) {
        setSocials(savedSocials);
      }
    } catch (error) {
      console.error("Error loading user data:", error);
    }
  }, []);

  // Save skills to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem("userSkills", JSON.stringify(skills));
    } catch (error) {
      console.error("Error saving skills:", error);
    }
  }, [skills]);

  // Save profile photo to localStorage whenever it changes
  useEffect(() => {
    try {
      if (profilePhoto) {
        localStorage.setItem("profilePhoto", profilePhoto);
      } else {
        localStorage.removeItem("profilePhoto");
      }
    } catch (error) {
      console.error("Error saving profile photo:", error);
    }
  }, [profilePhoto]);

  // Save social links to localStorage whenever they change
  useEffect(() => {
    try {
      localStorage.setItem("userSocials", JSON.stringify(socials));
    } catch (error) {
      console.error("Error saving social links:", error);
    }
  }, [socials]);

  const handleOpenEditProfile = () => {
    if (user) {
      setProfileFormData({
        name: user.name || "",
        title: user.title || "Software Developer",
      });
    }
    setEditProfileModal(true);
  };

  const handleSaveProfile = () => {
    if (!profileFormData.name.trim()) {
      alert("Please enter a name");
      return;
    }
    try {
      const updatedUser = {
        ...user,
        name: profileFormData.name.trim(),
        title: profileFormData.title.trim() || "Software Developer",
      };
      localStorage.setItem("user", JSON.stringify(updatedUser));
      setUserState(updatedUser);
      setEditProfileModal(false);
    } catch (error) {
      alert("Error saving profile: " + error.message);
    }
  };

  const handlePhotoChange = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (event) => {
        setProfilePhoto(event.target?.result);
      };
      reader.readAsDataURL(file);
    }
  };

  const triggerFileInput = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="profile-container">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handlePhotoChange}
        style={{ display: "none" }}
      />

      <div className="profile-header">
        <div className="profile-avatar-section">
          <div
            className="profile-avatar-large"
            onClick={triggerFileInput}
            title="Click to change profile photo"
            style={{ cursor: "pointer", position: "relative" }}
          >
            {profilePhoto ? (
              <img
                src={profilePhoto}
                alt="Profile"
                style={{
                  width: "100%",
                  height: "100%",
                  borderRadius: "50%",
                  objectFit: "cover",
                }}
              />
            ) : (
              <div className="profile-avatar-fallback">{initials}</div>
            )}
            <div className="avatar-edit-overlay">
              <Camera className="avatar-edit-icon" aria-hidden="true" />
            </div>
          </div>
          <div className="profile-name-section">
            <h2>{user?.name || "Candidate"}</h2>
            <p>{user?.title || "Software Developer"}</p>
            <p className="profile-email">{user?.email || "—"}</p>
          </div>
        </div>
        <button className="btn-edit-profile" onClick={handleOpenEditProfile}>
          Edit Profile
        </button>
      </div>

      <div className="profile-sections">
        {/* Skills Section */}
        <div className="profile-section-card">
          <div className="profile-section-header">
            <h3>Skills</h3>
            <button className="btn-add" onClick={() => setShowSkillsForm(true)}>
              + Add Skills
            </button>
          </div>
          <div className="skills-field">
            {/* Display selected skills as blue tags */}
            {skills.length > 0 && (
              <div className="skills-display">
                {skills.map((skill) => (
                  <div key={skill} className="skill-tag">
                    {skill}
                    <button
                      className="skill-remove"
                      onClick={() => handleRemoveSkill(skill)}
                      title="Remove skill"
                      type="button"
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            )}

            {/* Search dropdown - only show when form is active */}
            {showSkillsForm && (
              <div className="skills-dropdown-wrapper" ref={skillsDropdownRef}>
                <input
                  type="text"
                  placeholder="Search and add skills..."
                  value={skillSearch}
                  onChange={(e) => setSkillSearch(e.target.value)}
                  onFocus={() => setSkillsDropdown(true)}
                  className="skills-search-box"
                  autoComplete="off"
                  autoFocus
                />

                {skillsDropdown && (
                  <div className="skills-dropdown">
                    {skillSearch.trim() === "" ? (
                      <div className="dropdown-empty">
                        Type to search skills...
                      </div>
                    ) : filteredSkills.length === 0 ? (
                      <div className="dropdown-empty">
                        No skills found
                      </div>
                    ) : (
                      filteredSkills.map((skill) => (
                        <button
                          key={skill}
                          className="dropdown-item"
                          onClick={() => {
                            handleAddSkill(skill);
                          }}
                          type="button"
                        >
                          {skill}
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Socials Section */}
        <div className="profile-section-card">
          <div className="profile-section-header">
            <h3>Social Links</h3>
            <button className="btn-add" onClick={() => setEditingSocials(!editingSocials)}>
              {editingSocials ? "Done" : "Edit"}
            </button>
          </div>
          
          {editingSocials ? (
            <div className="socials-edit-form">
              <div className="form-group">
                <label>LinkedIn Profile</label>
                <input
                  type="url"
                  value={socials.linkedin}
                  onChange={(e) => setSocials({ ...socials, linkedin: e.target.value })}
                  placeholder="https://linkedin.com/in/yourprofile"
                />
              </div>
              <div className="form-group">
                <label>GitHub Profile</label>
                <input
                  type="url"
                  value={socials.github}
                  onChange={(e) => setSocials({ ...socials, github: e.target.value })}
                  placeholder="https://github.com/yourprofile"
                />
              </div>
            </div>
          ) : (
            <div className="socials-display">
              {socials.linkedin || socials.github ? (
                <div className="social-links">
                  {socials.linkedin && (
                    <a href={socials.linkedin} target="_blank" rel="noopener noreferrer" className="social-link linkedin">
                      <span className="social-icon">in</span>
                      <span className="social-label">LinkedIn</span>
                    </a>
                  )}
                  {socials.github && (
                    <a href={socials.github} target="_blank" rel="noopener noreferrer" className="social-link github">
                      <span className="social-icon">⚙</span>
                      <span className="social-label">GitHub</span>
                    </a>
                  )}
                </div>
              ) : (
                <p className="no-socials">No social links added yet</p>
              )}
            </div>
          )}
        </div>

        {/* Experience Section */}
        <div className="profile-section-card">
          <div className="profile-section-header">
            <h3>Experience</h3>
            <button className="btn-add" onClick={handleAddExperience}>
              + Add Experience
            </button>
          </div>
          <div className="experience-list">
            {experience.map((exp) => (
              <div key={exp.id} className="experience-item">
                <div className="experience-header">
                  <div>
                    <h4>{exp.title || "Job Title"}</h4>
                    <p className="company-name">{exp.company || "Company"}</p>
                    <p className="experience-period">
                      {exp.startDate}
                      {exp.endDate ? ` - ${exp.endDate}` : " - Present"}
                    </p>
                  </div>
                  <button
                    className="btn-remove"
                    onClick={() => handleRemoveExperience(exp.id)}
                  >
                    ✕
                  </button>
                </div>
                <p className="experience-description">
                  {exp.description || "Add description..."}
                </p>
                <button
                  className="btn-edit-item"
                  onClick={() => setExpModal(exp.id)}
                >
                  Edit
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Education Section */}
        <div className="profile-section-card">
          <div className="profile-section-header">
            <h3>Education</h3>
            <button className="btn-add" onClick={handleAddEducation}>
              + Add Education
            </button>
          </div>
          <div className="education-list">
            {education.map((edu) => (
              <div key={edu.id} className="education-item">
                <div className="education-header">
                  <div>
                    <h4>{edu.degree || "Degree"}</h4>
                    <p className="institution-name">{edu.institution || "Institution"}</p>
                    <p className="education-period">{edu.graduationYear || "Year"}</p>
                  </div>
                  <button
                    className="btn-remove"
                    onClick={() => handleRemoveEducation(edu.id)}
                  >
                    ✕
                  </button>
                </div>
                <button
                  className="btn-edit-item"
                  onClick={() => setEduModal(edu.id)}
                >
                  Edit
                </button>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Experience Modal */}
      {expModal && (
        <div className="modal-overlay" onClick={() => setExpModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Edit Experience</h3>
              <button
                className="modal-close"
                onClick={() => setExpModal(false)}
              >
                ×
              </button>
            </div>

            <div className="modal-body">
              {experience.map((exp) => 
                exp.id === expModal ? (
                  <div key={exp.id} className="form-group">
                    <label>Job Title</label>
                    <input
                      type="text"
                      value={exp.title}
                      onChange={(e) =>
                        handleUpdateExperience(exp.id, "title", e.target.value)
                      }
                      placeholder="e.g. Software Developer"
                    />

                    <label>Company</label>
                    <input
                      type="text"
                      value={exp.company}
                      onChange={(e) =>
                        handleUpdateExperience(exp.id, "company", e.target.value)
                      }
                      placeholder="e.g. Tech Company Inc."
                    />

                    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
                      <div>
                        <label>Start Date</label>
                        <input
                          type="month"
                          value={exp.startDate}
                          onChange={(e) =>
                            handleUpdateExperience(
                              exp.id,
                              "startDate",
                              e.target.value
                            )
                          }
                        />
                      </div>
                      {!exp.current && (
                        <div>
                          <label>End Date</label>
                          <input
                            type="month"
                            value={exp.endDate || ""}
                            onChange={(e) =>
                              handleUpdateExperience(
                                exp.id,
                                "endDate",
                                e.target.value
                              )
                            }
                          />
                        </div>
                      )}
                    </div>

                    <label>
                      <input
                        type="checkbox"
                        checked={exp.current}
                        onChange={(e) =>
                          handleUpdateExperience(exp.id, "current", e.target.checked)
                        }
                      />
                      Currently working here
                    </label>

                    <label>Description</label>
                    <textarea
                      value={exp.description}
                      onChange={(e) =>
                        handleUpdateExperience(
                          exp.id,
                          "description",
                          e.target.value
                        )
                      }
                      placeholder="Describe your responsibilities and achievements..."
                      rows={4}
                    />
                  </div>
                ) : null
              )}
            </div>

            <div className="modal-footer">
              <button
                className="btn-cancel"
                onClick={() => setExpModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Education Modal */}
      {eduModal && (
        <div className="modal-overlay" onClick={() => setEduModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Edit Education</h3>
              <button
                className="modal-close"
                onClick={() => setEduModal(false)}
              >
                ×
              </button>
            </div>

            <div className="modal-body">
              {education.map((edu) =>
                edu.id === eduModal ? (
                  <div key={edu.id} className="form-group">
                    <label>Degree</label>
                    <input
                      type="text"
                      value={edu.degree}
                      onChange={(e) =>
                        handleUpdateEducation(edu.id, "degree", e.target.value)
                      }
                      placeholder="e.g. Bachelor of Technology"
                    />

                    <label>Institution</label>
                    <input
                      type="text"
                      value={edu.institution}
                      onChange={(e) =>
                        handleUpdateEducation(edu.id, "institution", e.target.value)
                      }
                      placeholder="e.g. University Name"
                    />

                    <label>Graduation Year</label>
                    <input
                      type="number"
                      value={edu.graduationYear}
                      onChange={(e) =>
                        handleUpdateEducation(edu.id, "graduationYear", e.target.value)
                      }
                      placeholder="2022"
                      min="1950"
                      max={new Date().getFullYear() + 10}
                    />
                  </div>
                ) : null
              )}
            </div>

            <div className="modal-footer">
              <button
                className="btn-cancel"
                onClick={() => setEduModal(false)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Profile Modal */}
      {editProfileModal && (
        <div className="modal-overlay" onClick={() => setEditProfileModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Edit Profile</h3>
              <button
                className="modal-close"
                onClick={() => setEditProfileModal(false)}
              >
                ×
              </button>
            </div>

            <div className="modal-body">
              <div className="edit-profile-content">
                {/* Profile Photo Section */}
                <div className="edit-photo-section">
                  <div
                    className="edit-photo-preview"
                    onClick={triggerFileInput}
                    style={{ cursor: "pointer" }}
                    title="Click to change photo"
                  >
                    {profilePhoto ? (
                      <img
                        src={profilePhoto}
                        alt="Profile"
                        style={{
                          width: "100%",
                          height: "100%",
                          borderRadius: "50%",
                          objectFit: "cover",
                        }}
                      />
                    ) : (
                      <div
                        style={{
                          width: "100%",
                          height: "100%",
                          borderRadius: "50%",
                          background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: "center",
                          color: "white",
                          fontSize: "36px",
                          fontWeight: "700",
                        }}
                      >
                        {initials}
                      </div>
                    )}
                    <div className="photo-edit-icon">
                      <Camera className="photo-edit-svg" aria-hidden="true" />
                    </div>
                  </div>
                  <p className="photo-hint">Click to change profile photo</p>
                </div>

                {/* Form Fields */}
                <div className="form-group">
                  <label>Full Name</label>
                  <input
                    type="text"
                    value={profileFormData.name}
                    onChange={(e) =>
                      setProfileFormData({
                        ...profileFormData,
                        name: e.target.value,
                      })
                    }
                    placeholder="Your full name"
                  />
                </div>

                <div className="form-group">
                  <label>Title / Headline</label>
                  <input
                    type="text"
                    value={profileFormData.title}
                    onChange={(e) =>
                      setProfileFormData({
                        ...profileFormData,
                        title: e.target.value,
                      })
                    }
                    placeholder="e.g. Software Developer"
                  />
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button
                className="btn-cancel"
                onClick={() => setEditProfileModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn-save"
                onClick={handleSaveProfile}
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}    </div>
  );
}