import os
import json
import secrets
from datetime import datetime, date
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
import db

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "cam5-university-secret-key-2026")

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    return str(obj)

def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(32)
    return session["csrf_token"]

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token)

def validate_csrf():
    token = request.form.get("csrf_token")
    expected = session.get("csrf_token")
    if not token or not expected or not secrets.compare_digest(token, expected):
        return False
    return True

def is_valid_date(date_str):
    try:
        if not date_str:
            return False
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except (ValueError, TypeError):
        return False

def sanitize_db_error(e):
    """
    Format database error message without exposing credentials or internal connection strings.
    """
    if isinstance(e, ValueError):
        return str(e)
    err_str = str(e)
    if "ORA-01017" in err_str:
        return "Authentication failed: Invalid database username or password. Please check your DB_PASSWORD in .env."
    elif "ORA-12541" in err_str or "ORA-12514" in err_str:
        return "Oracle Database connection unavailable. Please ensure your Oracle listener is active."
    return "Database query could not be completed. Please ensure your Oracle database service is running and credentials in .env are valid."

def build_remove_url(endpoint, remove_key):
    """
    Generate a URL for endpoint retaining all current request query parameters except remove_key.
    Ensures clearing one filter does not clear others.
    """
    params = {k: v for k, v in request.args.items() if k != remove_key and v is not None and str(v).strip() != ""}
    return url_for(endpoint, **params)

@app.route("/")
def index():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    analytics = {}
    stats = {}
    error_message = None
    try:
        analytics = db.get_analytics_dashboard_data()
        stats = analytics.get("stats", {})
    except Exception as e:
        error_message = sanitize_db_error(e)
        stats = {
            "TOTAL_UNIVERSITIES": 0, "TOTAL_DEPARTMENTS": 0, "TOTAL_FACULTY": 0,
            "TOTAL_STUDENTS": 0, "TOTAL_COURSES": 0, "TOTAL_CLASSROOMS": 0,
            "TOTAL_EXAMS": 0, "TOTAL_RESULTS": 0, "TOTAL_BOOKS": 0, "TOTAL_HOSTELS": 0
        }
        analytics = {
            "stats": stats,
            "students_by_dept": [],
            "faculty_by_dept": [],
            "courses_by_dept": [],
            "grade_distribution": [],
            "exams_by_course": [],
            "dept_by_university": [],
            "hostel_by_university": [],
            "classroom_summary": {"TOTAL_ROOMS": 0, "TOTAL_CAPACITY": 0, "AVG_CAPACITY": 0, "MIN_CAPACITY": 0, "MAX_CAPACITY": 0},
            "hostel_summary": {"TOTAL_HOSTELS": 0, "TOTAL_CAPACITY": 0, "AVG_CAPACITY": 0, "MIN_CAPACITY": 0, "MAX_CAPACITY": 0}
        }
    return render_template(
        "dashboard.html",
        stats=stats,
        analytics=analytics,
        chart_data_json=json.dumps(analytics, default=json_serial),
        active_page="dashboard",
        error_message=error_message
    )

@app.route("/university")
def university():
    search_query = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    
    records = []
    locations = []
    stats = {"TOTAL_UNIVERSITIES": 0, "TOTAL_LOCATIONS": 0}
    error_message = None

    try:
        locations = db.get_filter_locations()
        records = db.get_universities(search_term=search_query, location=location)
        stats = db.get_university_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("university", "q")
        })
    if location:
        active_filters.append({
            "id": "location",
            "label": f"Location: {location}",
            "remove_url": build_remove_url("university", "location")
        })

    return render_template(
        "university.html",
        records=records,
        search_query=search_query,
        selected_filters={"location": location},
        filter_options={"locations": locations},
        active_filters=active_filters,
        clear_search_url=build_remove_url("university", "q"),
        reset_url=url_for("university"),
        stats=stats,
        active_page="university",
        error_message=error_message
    )

@app.route("/students")
def students():
    search_query = request.args.get("q", "").strip()
    dept_id = request.args.get("dept_id", "").strip()
    gender = request.args.get("gender", "").strip().upper()

    student_list = []
    departments = []
    stats = {"TOTAL_STUDENTS": 0, "TOTAL_DEPARTMENTS": 0}
    error_message = None

    try:
        departments = db.get_filter_departments()
        student_list = db.get_students(search_term=search_query, dept_id=dept_id, gender=gender)
        stats = db.get_student_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    # Resolve department name for active filter chip
    dept_map = {str(d["DEPT_ID"]): d["DEPT_NAME"] for d in departments}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("students", "q")
        })
    if dept_id:
        dname = dept_map.get(dept_id, f"Dept #{dept_id}")
        active_filters.append({
            "id": "dept_id",
            "label": f"Dept: {dname}",
            "remove_url": build_remove_url("students", "dept_id")
        })
    if gender:
        gname = "Male" if gender == "M" else ("Female" if gender == "F" else gender)
        active_filters.append({
            "id": "gender",
            "label": f"Gender: {gname}",
            "remove_url": build_remove_url("students", "gender")
        })

    return render_template(
        "students.html",
        students=student_list,
        search_query=search_query,
        selected_filters={"dept_id": dept_id, "gender": gender},
        filter_options={"departments": departments},
        active_filters=active_filters,
        clear_search_url=build_remove_url("students", "q"),
        reset_url=url_for("students"),
        stats=stats,
        active_page="students",
        error_message=error_message
    )

@app.route("/departments")
def departments():
    search_query = request.args.get("q", "").strip()
    unid = request.args.get("unid", "").strip()

    records = []
    universities = []
    stats = {"TOTAL_DEPARTMENTS": 0, "AFFILIATED_UNIVERSITIES": 0}
    error_message = None

    try:
        universities = db.get_filter_universities()
        records = db.get_departments(search_term=search_query, unid=unid)
        stats = db.get_department_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    univ_map = {str(u["UNID"]): u["UNAME"] for u in universities}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("departments", "q")
        })
    if unid:
        uname = univ_map.get(unid, f"Univ #{unid}")
        active_filters.append({
            "id": "unid",
            "label": f"University: {uname}",
            "remove_url": build_remove_url("departments", "unid")
        })

    return render_template(
        "departments.html",
        records=records,
        search_query=search_query,
        selected_filters={"unid": unid},
        filter_options={"universities": universities},
        active_filters=active_filters,
        clear_search_url=build_remove_url("departments", "q"),
        reset_url=url_for("departments"),
        stats=stats,
        active_page="departments",
        error_message=error_message
    )

@app.route("/faculty")
def faculty():
    search_query = request.args.get("q", "").strip()
    dept_id = request.args.get("dept_id", "").strip()
    designation = request.args.get("designation", "").strip()

    records = []
    departments = []
    designations = []
    stats = {"TOTAL_FACULTY": 0, "TOTAL_DEPARTMENTS": 0, "AVG_SALARY": 0}
    error_message = None

    try:
        departments = db.get_filter_departments()
        designations = db.get_filter_faculty_designations()
        records = db.get_faculty(search_term=search_query, dept_id=dept_id, designation=designation)
        stats = db.get_faculty_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    dept_map = {str(d["DEPT_ID"]): d["DEPT_NAME"] for d in departments}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("faculty", "q")
        })
    if dept_id:
        dname = dept_map.get(dept_id, f"Dept #{dept_id}")
        active_filters.append({
            "id": "dept_id",
            "label": f"Dept: {dname}",
            "remove_url": build_remove_url("faculty", "dept_id")
        })
    if designation:
        active_filters.append({
            "id": "designation",
            "label": f"Role: {designation}",
            "remove_url": build_remove_url("faculty", "designation")
        })

    return render_template(
        "faculty.html",
        records=records,
        search_query=search_query,
        selected_filters={"dept_id": dept_id, "designation": designation},
        filter_options={"departments": departments, "designations": designations},
        active_filters=active_filters,
        clear_search_url=build_remove_url("faculty", "q"),
        reset_url=url_for("faculty"),
        stats=stats,
        active_page="faculty",
        error_message=error_message
    )

@app.route("/courses")
def courses():
    search_query = request.args.get("q", "").strip()
    dept_id = request.args.get("dept_id", "").strip()
    fid = request.args.get("fid", "").strip()

    records = []
    departments = []
    faculty_members = []
    stats = {"TOTAL_COURSES": 0, "TOTAL_CREDITS": 0, "TEACHING_FACULTY": 0}
    error_message = None

    try:
        departments = db.get_filter_departments()
        faculty_members = db.get_filter_faculty_members()
        records = db.get_courses(search_term=search_query, dept_id=dept_id, fid=fid)
        stats = db.get_course_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    dept_map = {str(d["DEPT_ID"]): d["DEPT_NAME"] for d in departments}
    faculty_map = {str(f["FID"]): f["FNAME"] for f in faculty_members}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("courses", "q")
        })
    if dept_id:
        dname = dept_map.get(dept_id, f"Dept #{dept_id}")
        active_filters.append({
            "id": "dept_id",
            "label": f"Dept: {dname}",
            "remove_url": build_remove_url("courses", "dept_id")
        })
    if fid:
        fname = faculty_map.get(fid, f"Faculty #{fid}")
        active_filters.append({
            "id": "fid",
            "label": f"Instructor: {fname}",
            "remove_url": build_remove_url("courses", "fid")
        })

    return render_template(
        "courses.html",
        records=records,
        search_query=search_query,
        selected_filters={"dept_id": dept_id, "fid": fid},
        filter_options={"departments": departments, "faculty_members": faculty_members},
        active_filters=active_filters,
        clear_search_url=build_remove_url("courses", "q"),
        reset_url=url_for("courses"),
        stats=stats,
        active_page="courses",
        error_message=error_message
    )

@app.route("/classrooms")
def classrooms():
    search_query = request.args.get("q", "").strip()
    dept_id = request.args.get("dept_id", "").strip()
    min_capacity = request.args.get("min_capacity", "").strip()

    records = []
    departments = []
    stats = {"TOTAL_ROOMS": 0, "TOTAL_CAPACITY": 0, "TOTAL_DEPARTMENTS": 0}
    error_message = None

    try:
        departments = db.get_filter_departments()
        records = db.get_classrooms(search_term=search_query, dept_id=dept_id, min_capacity=min_capacity)
        stats = db.get_classroom_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    dept_map = {str(d["DEPT_ID"]): d["DEPT_NAME"] for d in departments}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("classrooms", "q")
        })
    if dept_id:
        dname = dept_map.get(dept_id, f"Dept #{dept_id}")
        active_filters.append({
            "id": "dept_id",
            "label": f"Dept: {dname}",
            "remove_url": build_remove_url("classrooms", "dept_id")
        })
    if min_capacity:
        active_filters.append({
            "id": "min_capacity",
            "label": f"Min Capacity: {min_capacity}+",
            "remove_url": build_remove_url("classrooms", "min_capacity")
        })

    return render_template(
        "classrooms.html",
        records=records,
        search_query=search_query,
        selected_filters={"dept_id": dept_id, "min_capacity": min_capacity},
        filter_options={"departments": departments},
        active_filters=active_filters,
        clear_search_url=build_remove_url("classrooms", "q"),
        reset_url=url_for("classrooms"),
        stats=stats,
        active_page="classrooms",
        error_message=error_message
    )

@app.route("/examinations")
def examinations():
    search_query = request.args.get("q", "").strip()
    course_id = request.args.get("course_id", "").strip()
    exam_date = request.args.get("exam_date", "").strip()

    records = []
    courses = []
    exam_dates = []
    stats = {"TOTAL_EXAMS": 0, "ACTIVE_COURSES": 0, "ROOMS_UTILIZED": 0}
    error_message = None

    try:
        courses = db.get_filter_courses()
        exam_dates = db.get_filter_exam_dates()
        records = db.get_exams(search_term=search_query, course_id=course_id, exam_date=exam_date)
        stats = db.get_exam_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    course_map = {str(c["COURSE_ID"]): c["COURSE_NAME"] for c in courses}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("examinations", "q")
        })
    if course_id:
        cname = course_map.get(course_id, f"Course #{course_id}")
        active_filters.append({
            "id": "course_id",
            "label": f"Course: {cname}",
            "remove_url": build_remove_url("examinations", "course_id")
        })
    if exam_date:
        active_filters.append({
            "id": "exam_date",
            "label": f"Date: {exam_date}",
            "remove_url": build_remove_url("examinations", "exam_date")
        })

    return render_template(
        "examinations.html",
        records=records,
        search_query=search_query,
        selected_filters={"course_id": course_id, "exam_date": exam_date},
        filter_options={"courses": courses, "exam_dates": exam_dates},
        active_filters=active_filters,
        clear_search_url=build_remove_url("examinations", "q"),
        reset_url=url_for("examinations"),
        stats=stats,
        active_page="examinations",
        error_message=error_message
    )

@app.route("/results")
def results():
    search_query = request.args.get("q", "").strip()
    grade = request.args.get("grade", "").strip()
    min_marks = request.args.get("min_marks", "").strip()

    records = []
    grades = []
    stats = {"TOTAL_RESULTS": 0, "MAX_MARKS": 0, "AVG_MARKS": 0}
    error_message = None

    try:
        grades = db.get_filter_result_grades()
        records = db.get_results(search_term=search_query, grade=grade, min_marks=min_marks)
        stats = db.get_result_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("results", "q")
        })
    if grade:
        active_filters.append({
            "id": "grade",
            "label": f"Grade: {grade}",
            "remove_url": build_remove_url("results", "grade")
        })
    if min_marks:
        active_filters.append({
            "id": "min_marks",
            "label": f"Min Marks: {min_marks}+",
            "remove_url": build_remove_url("results", "min_marks")
        })

    return render_template(
        "results.html",
        records=records,
        search_query=search_query,
        selected_filters={"grade": grade, "min_marks": min_marks},
        filter_options={"grades": grades},
        active_filters=active_filters,
        clear_search_url=build_remove_url("results", "q"),
        reset_url=url_for("results"),
        stats=stats,
        active_page="results",
        error_message=error_message
    )

@app.route("/library")
def library():
    search_query = request.args.get("q", "").strip()
    unid = request.args.get("unid", "").strip()
    author = request.args.get("author", "").strip()

    records = []
    universities = []
    authors = []
    stats = {"TOTAL_BOOKS": 0, "UNIQUE_AUTHORS": 0, "CAMPUS_LIBRARIES": 0}
    error_message = None

    try:
        universities = db.get_filter_universities()
        authors = db.get_filter_library_authors()
        records = db.get_library(search_term=search_query, unid=unid, author=author)
        stats = db.get_library_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    univ_map = {str(u["UNID"]): u["UNAME"] for u in universities}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("library", "q")
        })
    if unid:
        uname = univ_map.get(unid, f"Univ #{unid}")
        active_filters.append({
            "id": "unid",
            "label": f"Campus: {uname}",
            "remove_url": build_remove_url("library", "unid")
        })
    if author:
        active_filters.append({
            "id": "author",
            "label": f"Author: {author}",
            "remove_url": build_remove_url("library", "author")
        })

    return render_template(
        "library.html",
        records=records,
        search_query=search_query,
        selected_filters={"unid": unid, "author": author},
        filter_options={"universities": universities, "authors": authors},
        active_filters=active_filters,
        clear_search_url=build_remove_url("library", "q"),
        reset_url=url_for("library"),
        stats=stats,
        active_page="library",
        error_message=error_message
    )

@app.route("/hostel")
def hostel():
    search_query = request.args.get("q", "").strip()
    unid = request.args.get("unid", "").strip()
    min_capacity = request.args.get("min_capacity", "").strip()

    records = []
    universities = []
    stats = {"TOTAL_HOSTELS": 0, "TOTAL_CAPACITY": 0, "CAMPUSES_SERVED": 0}
    error_message = None

    try:
        universities = db.get_filter_universities()
        records = db.get_hostels(search_term=search_query, unid=unid, min_capacity=min_capacity)
        stats = db.get_hostel_stats()
    except Exception as e:
        error_message = sanitize_db_error(e)

    univ_map = {str(u["UNID"]): u["UNAME"] for u in universities}

    active_filters = []
    if search_query:
        active_filters.append({
            "id": "q",
            "label": f'Search: "{search_query}"',
            "remove_url": build_remove_url("hostel", "q")
        })
    if unid:
        uname = univ_map.get(unid, f"Univ #{unid}")
        active_filters.append({
            "id": "unid",
            "label": f"Campus: {uname}",
            "remove_url": build_remove_url("hostel", "unid")
        })
    if min_capacity:
        active_filters.append({
            "id": "min_capacity",
            "label": f"Min Capacity: {min_capacity}+",
            "remove_url": build_remove_url("hostel", "min_capacity")
        })

    return render_template(
        "hostel.html",
        records=records,
        search_query=search_query,
        selected_filters={"unid": unid, "min_capacity": min_capacity},
        filter_options={"universities": universities},
        active_filters=active_filters,
        clear_search_url=build_remove_url("hostel", "q"),
        reset_url=url_for("hostel"),
        stats=stats,
        active_page="hostel",
        error_message=error_message
    )

# ==============================================================================
# Add Record Routes (POST/GET, Server Validation, CSRF Protection, Parameterized)
# ==============================================================================

# 1. Add University
@app.route("/university/add", methods=["GET", "POST"])
def add_university():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("UNIVERSITY1143", "UNID")

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_university.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                active_page="university"
            ), 400

        form_data = request.form.to_dict()
        unid_raw = form_data.get("unid", "").strip()
        uname = form_data.get("uname", "").strip()
        location = form_data.get("location", "").strip()

        if not unid_raw:
            errors["unid"] = "University ID is required."
        elif not unid_raw.isdigit() or int(unid_raw) <= 0:
            errors["unid"] = "University ID must be a positive integer."
        elif db.check_id_exists("UNIVERSITY1143", "UNID", int(unid_raw)):
            errors["unid"] = f"University ID {unid_raw} already exists."

        if not uname:
            errors["uname"] = "University name is required."
        elif len(uname) > 100:
            errors["uname"] = "University name cannot exceed 100 characters."

        if not location:
            errors["location"] = "Campus location is required."
        elif len(location) > 100:
            errors["location"] = "Location cannot exceed 100 characters."

        if not errors:
            try:
                db.insert_university(int(unid_raw), uname, location)
                flash(f"University '{uname}' (ID: {unid_raw}) successfully created.", "success")
                return redirect(url_for("university"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_university.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            active_page="university"
        ), 400

    return render_template(
        "add_university.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        active_page="university"
    )

# 2. Add Department
@app.route("/departments/add", methods=["GET", "POST"])
def add_department():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("DEPARTMENT1143", "DEPT_ID")
    dropdown_universities = db.get_universities_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_department.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_universities=dropdown_universities,
                active_page="departments"
            ), 400

        form_data = request.form.to_dict()
        dept_id_raw = form_data.get("dept_id", "").strip()
        dept_name = form_data.get("dept_name", "").strip()
        unid_raw = form_data.get("unid", "").strip()

        if not dept_id_raw:
            errors["dept_id"] = "Department ID is required."
        elif not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
            errors["dept_id"] = "Department ID must be a positive integer."
        elif db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
            errors["dept_id"] = f"Department ID {dept_id_raw} already exists."

        if not dept_name:
            errors["dept_name"] = "Department name is required."
        elif len(dept_name) > 100:
            errors["dept_name"] = "Department name cannot exceed 100 characters."

        unid_val = None
        if unid_raw:
            if not unid_raw.isdigit() or int(unid_raw) <= 0:
                errors["unid"] = "Invalid university selection."
            elif not db.check_id_exists("UNIVERSITY1143", "UNID", int(unid_raw)):
                errors["unid"] = "Selected university does not exist."
            else:
                unid_val = int(unid_raw)

        if not errors:
            try:
                db.insert_department(int(dept_id_raw), dept_name, unid_val)
                flash(f"Department '{dept_name}' (ID: {dept_id_raw}) successfully created.", "success")
                return redirect(url_for("departments"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_department.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_universities=dropdown_universities,
            active_page="departments"
        ), 400

    return render_template(
        "add_department.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_universities=dropdown_universities,
        active_page="departments"
    )

# 3. Add Faculty
@app.route("/faculty/add", methods=["GET", "POST"])
def add_faculty():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("FACULTY1143", "FID")
    dropdown_departments = db.get_departments_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_faculty.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_departments=dropdown_departments,
                active_page="faculty"
            ), 400

        form_data = request.form.to_dict()
        fid_raw = form_data.get("fid", "").strip()
        fname = form_data.get("fname", "").strip()
        designation = form_data.get("designation", "").strip()
        salary_raw = form_data.get("salary", "").strip()
        dept_id_raw = form_data.get("dept_id", "").strip()

        if not fid_raw:
            errors["fid"] = "Faculty ID is required."
        elif not fid_raw.isdigit() or int(fid_raw) <= 0:
            errors["fid"] = "Faculty ID must be a positive integer."
        elif db.check_id_exists("FACULTY1143", "FID", int(fid_raw)):
            errors["fid"] = f"Faculty ID {fid_raw} already exists."

        if not fname:
            errors["fname"] = "Faculty name is required."
        elif len(fname) > 100:
            errors["fname"] = "Name cannot exceed 100 characters."

        if designation and len(designation) > 50:
            errors["designation"] = "Designation cannot exceed 50 characters."

        salary_val = None
        if not salary_raw:
            errors["salary"] = "Salary is required."
        else:
            try:
                salary_val = float(salary_raw)
                if salary_val <= 0:
                    errors["salary"] = "Salary must be greater than 0 (salary > 0 constraint)."
            except ValueError:
                errors["salary"] = "Salary must be a valid numeric amount."

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        if not errors:
            try:
                db.insert_faculty(int(fid_raw), fname, designation, salary_val, dept_val)
                flash(f"Faculty member '{fname}' (ID: {fid_raw}) successfully registered.", "success")
                return redirect(url_for("faculty"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_faculty.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_departments=dropdown_departments,
            active_page="faculty"
        ), 400

    return render_template(
        "add_faculty.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_departments=dropdown_departments,
        active_page="faculty"
    )

# 4. Add Student
@app.route("/students/add", methods=["GET", "POST"])
def add_student():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("STUDENT1143", "SID")
    dropdown_departments = db.get_departments_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_student.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_departments=dropdown_departments,
                active_page="students"
            ), 400

        form_data = request.form.to_dict()
        sid_raw = form_data.get("sid", "").strip()
        sname = form_data.get("sname", "").strip()
        dob_raw = form_data.get("dob", "").strip()
        gender = form_data.get("gender", "").strip().upper()
        address = form_data.get("address", "").strip()
        dept_id_raw = form_data.get("dept_id", "").strip()

        if not sid_raw:
            errors["sid"] = "Student ID is required."
        elif not sid_raw.isdigit() or int(sid_raw) <= 0:
            errors["sid"] = "Student ID must be a positive integer."
        elif db.check_id_exists("STUDENT1143", "SID", int(sid_raw)):
            errors["sid"] = f"Student ID {sid_raw} already exists."

        if not sname:
            errors["sname"] = "Student name is required."
        elif len(sname) > 100:
            errors["sname"] = "Student name cannot exceed 100 characters."

        if not dob_raw:
            errors["dob"] = "Date of Birth is required."
        elif not is_valid_date(dob_raw):
            errors["dob"] = "Invalid date format. Please use YYYY-MM-DD."

        if not gender:
            errors["gender"] = "Gender is required."
        elif gender not in ("M", "F", "O"):
            errors["gender"] = "Gender must be 'M' (Male), 'F' (Female), or 'O' (Other)."

        if address and len(address) > 100:
            errors["address"] = "Address cannot exceed 100 characters."

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        if not errors:
            try:
                db.insert_student(int(sid_raw), sname, dob_raw, gender, address, dept_val)
                flash(f"Student '{sname}' (ID: {sid_raw}) successfully enrolled.", "success")
                return redirect(url_for("students"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_student.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_departments=dropdown_departments,
            active_page="students"
        ), 400

    return render_template(
        "add_student.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_departments=dropdown_departments,
        active_page="students"
    )

# 5. Add Course
@app.route("/courses/add", methods=["GET", "POST"])
def add_course():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("COURSE1143", "COURSE_ID")
    dropdown_departments = db.get_departments_dropdown()
    dropdown_faculty = db.get_faculty_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_course.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_departments=dropdown_departments,
                dropdown_faculty=dropdown_faculty,
                active_page="courses"
            ), 400

        form_data = request.form.to_dict()
        cid_raw = form_data.get("course_id", "").strip()
        cname = form_data.get("course_name", "").strip()
        credits_raw = form_data.get("credits", "").strip()
        dept_id_raw = form_data.get("dept_id", "").strip()
        fid_raw = form_data.get("fid", "").strip()

        if not cid_raw:
            errors["course_id"] = "Course ID is required."
        elif not cid_raw.isdigit() or int(cid_raw) <= 0:
            errors["course_id"] = "Course ID must be a positive integer."
        elif db.check_id_exists("COURSE1143", "COURSE_ID", int(cid_raw)):
            errors["course_id"] = f"Course ID {cid_raw} already exists."

        if not cname:
            errors["course_name"] = "Course name is required."
        elif len(cname) > 100:
            errors["course_name"] = "Course name cannot exceed 100 characters."

        credits_val = None
        if credits_raw:
            if not credits_raw.isdigit() or int(credits_raw) <= 0:
                errors["credits"] = "Credits must be a positive integer."
            else:
                credits_val = int(credits_raw)

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        fid_val = None
        if fid_raw:
            if not fid_raw.isdigit() or int(fid_raw) <= 0:
                errors["fid"] = "Invalid faculty selection."
            elif not db.check_id_exists("FACULTY1143", "FID", int(fid_raw)):
                errors["fid"] = "Selected faculty instructor does not exist."
            else:
                fid_val = int(fid_raw)

        if not errors:
            try:
                db.insert_course(int(cid_raw), cname, credits_val, dept_val, fid_val)
                flash(f"Course '{cname}' (ID: {cid_raw}) successfully created.", "success")
                return redirect(url_for("courses"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_course.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_departments=dropdown_departments,
            dropdown_faculty=dropdown_faculty,
            active_page="courses"
        ), 400

    return render_template(
        "add_course.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_departments=dropdown_departments,
        dropdown_faculty=dropdown_faculty,
        active_page="courses"
    )

# 6. Add Classroom
@app.route("/classrooms/add", methods=["GET", "POST"])
def add_classroom():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("CLASSROOM1143", "ROOM_NO")
    dropdown_departments = db.get_departments_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_classroom.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_departments=dropdown_departments,
                active_page="classrooms"
            ), 400

        form_data = request.form.to_dict()
        room_raw = form_data.get("room_no", "").strip()
        cap_raw = form_data.get("capacity", "").strip()
        dept_id_raw = form_data.get("dept_id", "").strip()

        if not room_raw:
            errors["room_no"] = "Room number is required."
        elif not room_raw.isdigit() or int(room_raw) <= 0:
            errors["room_no"] = "Room number must be a positive integer."
        elif db.check_id_exists("CLASSROOM1143", "ROOM_NO", int(room_raw)):
            errors["room_no"] = f"Room {room_raw} already exists."

        cap_val = None
        if not cap_raw:
            errors["capacity"] = "Seating capacity is required."
        elif not cap_raw.isdigit() or int(cap_raw) <= 0:
            errors["capacity"] = "Capacity must be greater than 0 (capacity > 0 constraint)."
        else:
            cap_val = int(cap_raw)

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        if not errors:
            try:
                db.insert_classroom(int(room_raw), cap_val, dept_val)
                flash(f"Classroom {room_raw} (Capacity: {cap_val}) successfully registered.", "success")
                return redirect(url_for("classrooms"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_classroom.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_departments=dropdown_departments,
            active_page="classrooms"
        ), 400

    return render_template(
        "add_classroom.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_departments=dropdown_departments,
        active_page="classrooms"
    )

# 7. Add Examination
@app.route("/examinations/add", methods=["GET", "POST"])
def add_examination():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("EXAM1143", "EXAM_ID")
    dropdown_courses = db.get_courses_dropdown()
    dropdown_classrooms = db.get_classrooms_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_exam.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_courses=dropdown_courses,
                dropdown_classrooms=dropdown_classrooms,
                active_page="examinations"
            ), 400

        form_data = request.form.to_dict()
        eid_raw = form_data.get("exam_id", "").strip()
        ename = form_data.get("exam_name", "").strip()
        edate_raw = form_data.get("exam_date", "").strip()
        cid_raw = form_data.get("course_id", "").strip()
        room_raw = form_data.get("room_no", "").strip()

        if not eid_raw:
            errors["exam_id"] = "Exam ID is required."
        elif not eid_raw.isdigit() or int(eid_raw) <= 0:
            errors["exam_id"] = "Exam ID must be a positive integer."
        elif db.check_id_exists("EXAM1143", "EXAM_ID", int(eid_raw)):
            errors["exam_id"] = f"Exam ID {eid_raw} already exists."

        if not ename:
            errors["exam_name"] = "Exam name is required."
        elif len(ename) > 100:
            errors["exam_name"] = "Exam name cannot exceed 100 characters."

        if not edate_raw:
            errors["exam_date"] = "Exam date is required."
        elif not is_valid_date(edate_raw):
            errors["exam_date"] = "Invalid date format. Please use YYYY-MM-DD."

        cid_val = None
        if cid_raw:
            if not cid_raw.isdigit() or int(cid_raw) <= 0:
                errors["course_id"] = "Invalid course selection."
            elif not db.check_id_exists("COURSE1143", "COURSE_ID", int(cid_raw)):
                errors["course_id"] = "Selected course does not exist."
            else:
                cid_val = int(cid_raw)

        room_val = None
        if room_raw:
            if not room_raw.isdigit() or int(room_raw) <= 0:
                errors["room_no"] = "Invalid classroom venue selection."
            elif not db.check_id_exists("CLASSROOM1143", "ROOM_NO", int(room_raw)):
                errors["room_no"] = "Selected classroom venue does not exist."
            else:
                room_val = int(room_raw)

        if not errors:
            try:
                db.insert_exam(int(eid_raw), ename, edate_raw, cid_val, room_val)
                flash(f"Examination '{ename}' (ID: {eid_raw}) scheduled successfully.", "success")
                return redirect(url_for("examinations"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_exam.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_courses=dropdown_courses,
            dropdown_classrooms=dropdown_classrooms,
            active_page="examinations"
        ), 400

    return render_template(
        "add_exam.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_courses=dropdown_courses,
        dropdown_classrooms=dropdown_classrooms,
        active_page="examinations"
    )

# 8. Add Result
@app.route("/results/add", methods=["GET", "POST"])
def add_result():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("RESULT1143", "RESULT_ID")
    dropdown_students = db.get_students_dropdown()
    dropdown_exams = db.get_exams_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_result.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_students=dropdown_students,
                dropdown_exams=dropdown_exams,
                active_page="results"
            ), 400

        form_data = request.form.to_dict()
        rid_raw = form_data.get("result_id", "").strip()
        sid_raw = form_data.get("sid", "").strip()
        eid_raw = form_data.get("exam_id", "").strip()
        marks_raw = form_data.get("marks", "").strip()
        grade = form_data.get("grade", "").strip().upper()

        if not rid_raw:
            errors["result_id"] = "Result ID is required."
        elif not rid_raw.isdigit() or int(rid_raw) <= 0:
            errors["result_id"] = "Result ID must be a positive integer."
        elif db.check_id_exists("RESULT1143", "RESULT_ID", int(rid_raw)):
            errors["result_id"] = f"Result ID {rid_raw} already exists."

        sid_val = None
        if not sid_raw:
            errors["sid"] = "Student selection is required."
        elif not sid_raw.isdigit() or int(sid_raw) <= 0:
            errors["sid"] = "Invalid student selection."
        elif not db.check_id_exists("STUDENT1143", "SID", int(sid_raw)):
            errors["sid"] = "Selected student does not exist."
        else:
            sid_val = int(sid_raw)

        eid_val = None
        if not eid_raw:
            errors["exam_id"] = "Examination selection is required."
        elif not eid_raw.isdigit() or int(eid_raw) <= 0:
            errors["exam_id"] = "Invalid examination selection."
        elif not db.check_id_exists("EXAM1143", "EXAM_ID", int(eid_raw)):
            errors["exam_id"] = "Selected examination does not exist."
        else:
            eid_val = int(eid_raw)

        marks_val = None
        if not marks_raw:
            errors["marks"] = "Marks obtained is required."
        else:
            try:
                marks_val = float(marks_raw)
                if marks_val < 0 or marks_val > 100:
                    errors["marks"] = "Marks must be between 0 and 100 (check constraint)."
            except ValueError:
                errors["marks"] = "Marks must be a numeric score."

        if not grade:
            errors["grade"] = "Letter grade is required."
        elif grade not in ("S", "A", "B", "C", "D", "E", "F"):
            errors["grade"] = "Grade must be S, A, B, C, D, E, or F."

        if not errors:
            try:
                db.insert_result(int(rid_raw), grade, marks_val, sid_val, eid_val)
                flash(f"Exam Result #{rid_raw} (Grade: {grade}, Marks: {marks_val}) successfully recorded.", "success")
                return redirect(url_for("results"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_result.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_students=dropdown_students,
            dropdown_exams=dropdown_exams,
            active_page="results"
        ), 400

    return render_template(
        "add_result.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_students=dropdown_students,
        dropdown_exams=dropdown_exams,
        active_page="results"
    )

# 9. Add Library Book
@app.route("/library/add", methods=["GET", "POST"])
def add_library():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("LIBRARY1143", "BOOK_ID")
    dropdown_universities = db.get_universities_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_library.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_universities=dropdown_universities,
                active_page="library"
            ), 400

        form_data = request.form.to_dict()
        bid_raw = form_data.get("book_id", "").strip()
        title = form_data.get("title", "").strip()
        author = form_data.get("author", "").strip()
        unid_raw = form_data.get("unid", "").strip()

        if not bid_raw:
            errors["book_id"] = "Book ID is required."
        elif not bid_raw.isdigit() or int(bid_raw) <= 0:
            errors["book_id"] = "Book ID must be a positive integer."
        elif db.check_id_exists("LIBRARY1143", "BOOK_ID", int(bid_raw)):
            errors["book_id"] = f"Book ID {bid_raw} already exists."

        if not title:
            errors["title"] = "Book title is required."
        elif len(title) > 100:
            errors["title"] = "Title cannot exceed 100 characters."

        if not author:
            errors["author"] = "Author name is required."
        elif len(author) > 100:
            errors["author"] = "Author cannot exceed 100 characters."

        unid_val = None
        if unid_raw:
            if not unid_raw.isdigit() or int(unid_raw) <= 0:
                errors["unid"] = "Invalid university selection."
            elif not db.check_id_exists("UNIVERSITY1143", "UNID", int(unid_raw)):
                errors["unid"] = "Selected university does not exist."
            else:
                unid_val = int(unid_raw)

        if not errors:
            try:
                db.insert_library(int(bid_raw), title, author, unid_val)
                flash(f"Book '{title}' (ID: {bid_raw}) cataloged successfully.", "success")
                return redirect(url_for("library"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_library.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_universities=dropdown_universities,
            active_page="library"
        ), 400

    return render_template(
        "add_library.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_universities=dropdown_universities,
        active_page="library"
    )

# 10. Add Hostel
@app.route("/hostel/add", methods=["GET", "POST"])
def add_hostel():
    errors = {}
    form_error = None
    form_data = {}
    suggested_id = db.get_next_id("HOSTEL1143", "HOSTEL_ID")
    dropdown_universities = db.get_universities_dropdown()

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_hostel.html",
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=suggested_id,
                dropdown_universities=dropdown_universities,
                active_page="hostel"
            ), 400

        form_data = request.form.to_dict()
        hid_raw = form_data.get("hostel_id", "").strip()
        hname = form_data.get("hostel_name", "").strip()
        cap_raw = form_data.get("capacity", "").strip()
        unid_raw = form_data.get("unid", "").strip()

        if not hid_raw:
            errors["hostel_id"] = "Hostel ID is required."
        elif not hid_raw.isdigit() or int(hid_raw) <= 0:
            errors["hostel_id"] = "Hostel ID must be a positive integer."
        elif db.check_id_exists("HOSTEL1143", "HOSTEL_ID", int(hid_raw)):
            errors["hostel_id"] = f"Hostel ID {hid_raw} already exists."

        if not hname:
            errors["hostel_name"] = "Hostel hall name is required."
        elif len(hname) > 100:
            errors["hostel_name"] = "Hostel name cannot exceed 100 characters."

        cap_val = None
        if not cap_raw:
            errors["capacity"] = "Resident capacity is required."
        elif not cap_raw.isdigit() or int(cap_raw) <= 0:
            errors["capacity"] = "Capacity must be greater than 0 (capacity > 0 constraint)."
        else:
            cap_val = int(cap_raw)

        unid_val = None
        if unid_raw:
            if not unid_raw.isdigit() or int(unid_raw) <= 0:
                errors["unid"] = "Invalid university selection."
            elif not db.check_id_exists("UNIVERSITY1143", "UNID", int(unid_raw)):
                errors["unid"] = "Selected university does not exist."
            else:
                unid_val = int(unid_raw)

        if not errors:
            try:
                db.insert_hostel(int(hid_raw), hname, cap_val, unid_val)
                flash(f"Hostel hall '{hname}' (ID: {hid_raw}) registered successfully.", "success")
                return redirect(url_for("hostel"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_hostel.html",
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=suggested_id,
            dropdown_universities=dropdown_universities,
            active_page="hostel"
        ), 400

    return render_template(
        "add_hostel.html",
        errors=errors,
        form_error=None,
        form_data=form_data,
        suggested_id=suggested_id,
        dropdown_universities=dropdown_universities,
        active_page="hostel"
    )

# ==============================================================================
# Edit & Delete Routes (All 10 Tables, Server Validation, CSRF, Parameterized)
# ==============================================================================

# --- 1. UNIVERSITY ---
@app.route("/university/<int:unid>/edit", methods=["GET", "POST"])
def edit_university(unid):
    rec = db.get_university_by_id(unid)
    if not rec:
        flash(f"University record with ID {unid} does not exist.", "danger")
        return redirect(url_for("university"))

    errors = {}
    form_error = None
    form_data = {
        "unid": str(rec["UNID"]),
        "uname": rec["UNAME"],
        "location": rec["LOCATION"]
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_university.html",
                is_edit=True,
                action_url=url_for("edit_university", unid=unid),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=unid,
                active_page="university"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        uname = submitted.get("uname", "").strip()
        location = submitted.get("location", "").strip()

        if not uname:
            errors["uname"] = "University name is required."
        elif len(uname) > 100:
            errors["uname"] = "University name cannot exceed 100 characters."

        if not location:
            errors["location"] = "Campus location is required."
        elif len(location) > 100:
            errors["location"] = "Location cannot exceed 100 characters."

        if not errors:
            try:
                db.update_university(unid, uname, location)
                flash(f"University '{uname}' (ID: {unid}) updated successfully.", "success")
                return redirect(url_for("university"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_university.html",
            is_edit=True,
            action_url=url_for("edit_university", unid=unid),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=unid,
            active_page="university"
        ), 400

    return render_template(
        "add_university.html",
        is_edit=True,
        action_url=url_for("edit_university", unid=unid),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=unid,
        active_page="university"
    )

@app.route("/university/<int:unid>/delete", methods=["POST"])
def delete_university(unid):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("university"))
    try:
        db.delete_university(unid)
        flash(f"University record #{unid} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("university"))


# --- 2. DEPARTMENT ---
@app.route("/departments/<int:dept_id>/edit", methods=["GET", "POST"])
def edit_department(dept_id):
    rec = db.get_department_by_id(dept_id)
    if not rec:
        flash(f"Department record with ID {dept_id} does not exist.", "danger")
        return redirect(url_for("departments"))

    errors = {}
    form_error = None
    dropdown_universities = db.get_universities_dropdown()
    form_data = {
        "dept_id": str(rec["DEPT_ID"]),
        "dept_name": rec["DEPT_NAME"],
        "unid": str(rec["UNID"]) if rec["UNID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_department.html",
                is_edit=True,
                action_url=url_for("edit_department", dept_id=dept_id),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=dept_id,
                dropdown_universities=dropdown_universities,
                active_page="departments"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        dept_name = submitted.get("dept_name", "").strip()
        unid_raw = submitted.get("unid", "").strip()

        if not dept_name:
            errors["dept_name"] = "Department name is required."
        elif len(dept_name) > 100:
            errors["dept_name"] = "Department name cannot exceed 100 characters."

        unid_val = None
        if unid_raw:
            if not unid_raw.isdigit() or int(unid_raw) <= 0:
                errors["unid"] = "Invalid university selection."
            elif not db.check_id_exists("UNIVERSITY1143", "UNID", int(unid_raw)):
                errors["unid"] = "Selected university does not exist."
            else:
                unid_val = int(unid_raw)

        if not errors:
            try:
                db.update_department(dept_id, dept_name, unid_val)
                flash(f"Department '{dept_name}' (ID: {dept_id}) updated successfully.", "success")
                return redirect(url_for("departments"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_department.html",
            is_edit=True,
            action_url=url_for("edit_department", dept_id=dept_id),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=dept_id,
            dropdown_universities=dropdown_universities,
            active_page="departments"
        ), 400

    return render_template(
        "add_department.html",
        is_edit=True,
        action_url=url_for("edit_department", dept_id=dept_id),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=dept_id,
        dropdown_universities=dropdown_universities,
        active_page="departments"
    )

@app.route("/departments/<int:dept_id>/delete", methods=["POST"])
def delete_department(dept_id):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("departments"))
    try:
        db.delete_department(dept_id)
        flash(f"Department record #{dept_id} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("departments"))


# --- 3. FACULTY ---
@app.route("/faculty/<int:fid>/edit", methods=["GET", "POST"])
def edit_faculty(fid):
    rec = db.get_faculty_by_id(fid)
    if not rec:
        flash(f"Faculty record with ID {fid} does not exist.", "danger")
        return redirect(url_for("faculty"))

    errors = {}
    form_error = None
    dropdown_departments = db.get_departments_dropdown()
    form_data = {
        "fid": str(rec["FID"]),
        "fname": rec["FNAME"],
        "designation": rec["DESIGNATION"] or "",
        "salary": str(rec["SALARY"]) if rec["SALARY"] is not None else "",
        "dept_id": str(rec["DEPT_ID"]) if rec["DEPT_ID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_faculty.html",
                is_edit=True,
                action_url=url_for("edit_faculty", fid=fid),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=fid,
                dropdown_departments=dropdown_departments,
                active_page="faculty"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        fname = submitted.get("fname", "").strip()
        designation = submitted.get("designation", "").strip()
        salary_raw = submitted.get("salary", "").strip()
        dept_id_raw = submitted.get("dept_id", "").strip()

        if not fname:
            errors["fname"] = "Faculty name is required."
        elif len(fname) > 100:
            errors["fname"] = "Name cannot exceed 100 characters."

        if len(designation) > 100:
            errors["designation"] = "Designation cannot exceed 100 characters."

        salary_val = None
        if not salary_raw:
            errors["salary"] = "Salary is required."
        else:
            try:
                salary_val = float(salary_raw)
                if salary_val <= 0:
                    errors["salary"] = "Salary must be greater than 0 (salary > 0 constraint)."
            except ValueError:
                errors["salary"] = "Salary must be a valid numeric amount."

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        if not errors:
            try:
                db.update_faculty(fid, fname, designation, salary_val, dept_val)
                flash(f"Faculty '{fname}' (FID: {fid}) updated successfully.", "success")
                return redirect(url_for("faculty"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_faculty.html",
            is_edit=True,
            action_url=url_for("edit_faculty", fid=fid),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=fid,
            dropdown_departments=dropdown_departments,
            active_page="faculty"
        ), 400

    return render_template(
        "add_faculty.html",
        is_edit=True,
        action_url=url_for("edit_faculty", fid=fid),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=fid,
        dropdown_departments=dropdown_departments,
        active_page="faculty"
    )

@app.route("/faculty/<int:fid>/delete", methods=["POST"])
def delete_faculty(fid):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("faculty"))
    try:
        db.delete_faculty(fid)
        flash(f"Faculty record #{fid} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("faculty"))


# --- 4. STUDENT ---
@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
def edit_student(sid):
    rec = db.get_student_by_id(sid)
    if not rec:
        flash(f"Student record with ID {sid} does not exist.", "danger")
        return redirect(url_for("students"))

    errors = {}
    form_error = None
    dropdown_departments = db.get_departments_dropdown()
    form_data = {
        "sid": str(rec["SID"]),
        "sname": rec["SNAME"],
        "dob": rec["DOB"] or "",
        "gender": rec["GENDER"] or "",
        "address": rec["ADDRESS"] or "",
        "dept_id": str(rec["DEPT_ID"]) if rec["DEPT_ID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_student.html",
                is_edit=True,
                action_url=url_for("edit_student", sid=sid),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=sid,
                dropdown_departments=dropdown_departments,
                active_page="students"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        sname = submitted.get("sname", "").strip()
        dob_raw = submitted.get("dob", "").strip()
        gender = submitted.get("gender", "").strip().upper()
        address = submitted.get("address", "").strip()
        dept_id_raw = submitted.get("dept_id", "").strip()

        if not sname:
            errors["sname"] = "Student name is required."
        elif len(sname) > 100:
            errors["sname"] = "Name cannot exceed 100 characters."

        if not dob_raw:
            errors["dob"] = "Date of birth is required."
        elif not is_valid_date(dob_raw):
            errors["dob"] = "Invalid date format. Please use YYYY-MM-DD."

        if not gender:
            errors["gender"] = "Gender selection is required."
        elif gender not in ("M", "F", "O"):
            errors["gender"] = "Gender must be 'M', 'F', or 'O' (check constraint)."

        if len(address) > 100:
            errors["address"] = "Address cannot exceed 100 characters."

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        if not errors:
            try:
                db.update_student(sid, sname, dob_raw, gender, address, dept_val)
                flash(f"Student '{sname}' (SID: {sid}) updated successfully.", "success")
                return redirect(url_for("students"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_student.html",
            is_edit=True,
            action_url=url_for("edit_student", sid=sid),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=sid,
            dropdown_departments=dropdown_departments,
            active_page="students"
        ), 400

    return render_template(
        "add_student.html",
        is_edit=True,
        action_url=url_for("edit_student", sid=sid),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=sid,
        dropdown_departments=dropdown_departments,
        active_page="students"
    )

@app.route("/students/<int:sid>/delete", methods=["POST"])
def delete_student(sid):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("students"))
    try:
        db.delete_student(sid)
        flash(f"Student record #{sid} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("students"))


# --- 5. COURSE ---
@app.route("/courses/<int:course_id>/edit", methods=["GET", "POST"])
def edit_course(course_id):
    rec = db.get_course_by_id(course_id)
    if not rec:
        flash(f"Course record with ID {course_id} does not exist.", "danger")
        return redirect(url_for("courses"))

    errors = {}
    form_error = None
    dropdown_departments = db.get_departments_dropdown()
    dropdown_faculty = db.get_faculty_dropdown()
    form_data = {
        "course_id": str(rec["COURSE_ID"]),
        "course_name": rec["COURSE_NAME"],
        "credits": str(rec["CREDITS"]) if rec["CREDITS"] is not None else "",
        "dept_id": str(rec["DEPT_ID"]) if rec["DEPT_ID"] is not None else "",
        "fid": str(rec["FID"]) if rec["FID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_course.html",
                is_edit=True,
                action_url=url_for("edit_course", course_id=course_id),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=course_id,
                dropdown_departments=dropdown_departments,
                dropdown_faculty=dropdown_faculty,
                active_page="courses"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        cname = submitted.get("course_name", "").strip()
        credits_raw = submitted.get("credits", "").strip()
        dept_id_raw = submitted.get("dept_id", "").strip()
        fid_raw = submitted.get("fid", "").strip()

        if not cname:
            errors["course_name"] = "Course name is required."
        elif len(cname) > 100:
            errors["course_name"] = "Course name cannot exceed 100 characters."

        credits_val = None
        if credits_raw:
            if not credits_raw.isdigit() or int(credits_raw) <= 0:
                errors["credits"] = "Credits must be a positive integer."
            else:
                credits_val = int(credits_raw)

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        fid_val = None
        if fid_raw:
            if not fid_raw.isdigit() or int(fid_raw) <= 0:
                errors["fid"] = "Invalid faculty instructor selection."
            elif not db.check_id_exists("FACULTY1143", "FID", int(fid_raw)):
                errors["fid"] = "Selected faculty instructor does not exist."
            else:
                fid_val = int(fid_raw)

        if not errors:
            try:
                db.update_course(course_id, cname, credits_val, dept_val, fid_val)
                flash(f"Course '{cname}' (ID: {course_id}) updated successfully.", "success")
                return redirect(url_for("courses"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_course.html",
            is_edit=True,
            action_url=url_for("edit_course", course_id=course_id),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=course_id,
            dropdown_departments=dropdown_departments,
            dropdown_faculty=dropdown_faculty,
            active_page="courses"
        ), 400

    return render_template(
        "add_course.html",
        is_edit=True,
        action_url=url_for("edit_course", course_id=course_id),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=course_id,
        dropdown_departments=dropdown_departments,
        dropdown_faculty=dropdown_faculty,
        active_page="courses"
    )

@app.route("/courses/<int:course_id>/delete", methods=["POST"])
def delete_course(course_id):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("courses"))
    try:
        db.delete_course(course_id)
        flash(f"Course record #{course_id} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("courses"))


# --- 6. CLASSROOM ---
@app.route("/classrooms/<int:room_no>/edit", methods=["GET", "POST"])
def edit_classroom(room_no):
    rec = db.get_classroom_by_id(room_no)
    if not rec:
        flash(f"Classroom record with Room No {room_no} does not exist.", "danger")
        return redirect(url_for("classrooms"))

    errors = {}
    form_error = None
    dropdown_departments = db.get_departments_dropdown()
    form_data = {
        "room_no": str(rec["ROOM_NO"]),
        "capacity": str(rec["CAPACITY"]) if rec["CAPACITY"] is not None else "",
        "dept_id": str(rec["DEPT_ID"]) if rec["DEPT_ID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_classroom.html",
                is_edit=True,
                action_url=url_for("edit_classroom", room_no=room_no),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=room_no,
                dropdown_departments=dropdown_departments,
                active_page="classrooms"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        cap_raw = submitted.get("capacity", "").strip()
        dept_id_raw = submitted.get("dept_id", "").strip()

        cap_val = None
        if not cap_raw:
            errors["capacity"] = "Seating capacity is required."
        elif not cap_raw.isdigit() or int(cap_raw) <= 0:
            errors["capacity"] = "Capacity must be greater than 0 (capacity > 0 check constraint)."
        else:
            cap_val = int(cap_raw)

        dept_val = None
        if dept_id_raw:
            if not dept_id_raw.isdigit() or int(dept_id_raw) <= 0:
                errors["dept_id"] = "Invalid department selection."
            elif not db.check_id_exists("DEPARTMENT1143", "DEPT_ID", int(dept_id_raw)):
                errors["dept_id"] = "Selected department does not exist."
            else:
                dept_val = int(dept_id_raw)

        if not errors:
            try:
                db.update_classroom(room_no, cap_val, dept_val)
                flash(f"Classroom Hall {room_no} updated successfully.", "success")
                return redirect(url_for("classrooms"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_classroom.html",
            is_edit=True,
            action_url=url_for("edit_classroom", room_no=room_no),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=room_no,
            dropdown_departments=dropdown_departments,
            active_page="classrooms"
        ), 400

    return render_template(
        "add_classroom.html",
        is_edit=True,
        action_url=url_for("edit_classroom", room_no=room_no),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=room_no,
        dropdown_departments=dropdown_departments,
        active_page="classrooms"
    )

@app.route("/classrooms/<int:room_no>/delete", methods=["POST"])
def delete_classroom(room_no):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("classrooms"))
    try:
        db.delete_classroom(room_no)
        flash(f"Classroom Hall {room_no} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("classrooms"))


# --- 7. EXAM ---
@app.route("/examinations/<int:exam_id>/edit", methods=["GET", "POST"])
def edit_exam(exam_id):
    rec = db.get_exam_by_id(exam_id)
    if not rec:
        flash(f"Examination record with ID {exam_id} does not exist.", "danger")
        return redirect(url_for("examinations"))

    errors = {}
    form_error = None
    dropdown_courses = db.get_courses_dropdown()
    dropdown_classrooms = db.get_classrooms_dropdown()
    form_data = {
        "exam_id": str(rec["EXAM_ID"]),
        "exam_name": rec["EXAM_NAME"],
        "exam_date": rec["EXAM_DATE"] or "",
        "course_id": str(rec["COURSE_ID"]) if rec["COURSE_ID"] is not None else "",
        "room_no": str(rec["ROOM_NO"]) if rec["ROOM_NO"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_exam.html",
                is_edit=True,
                action_url=url_for("edit_exam", exam_id=exam_id),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=exam_id,
                dropdown_courses=dropdown_courses,
                dropdown_classrooms=dropdown_classrooms,
                active_page="examinations"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        ename = submitted.get("exam_name", "").strip()
        edate_raw = submitted.get("exam_date", "").strip()
        cid_raw = submitted.get("course_id", "").strip()
        room_raw = submitted.get("room_no", "").strip()

        if not ename:
            errors["exam_name"] = "Exam name is required."
        elif len(ename) > 100:
            errors["exam_name"] = "Exam name cannot exceed 100 characters."

        if not edate_raw:
            errors["exam_date"] = "Exam date is required."
        elif not is_valid_date(edate_raw):
            errors["exam_date"] = "Invalid date format. Please use YYYY-MM-DD."

        cid_val = None
        if cid_raw:
            if not cid_raw.isdigit() or int(cid_raw) <= 0:
                errors["course_id"] = "Invalid course selection."
            elif not db.check_id_exists("COURSE1143", "COURSE_ID", int(cid_raw)):
                errors["course_id"] = "Selected course does not exist."
            else:
                cid_val = int(cid_raw)

        room_val = None
        if room_raw:
            if not room_raw.isdigit() or int(room_raw) <= 0:
                errors["room_no"] = "Invalid classroom venue selection."
            elif not db.check_id_exists("CLASSROOM1143", "ROOM_NO", int(room_raw)):
                errors["room_no"] = "Selected classroom venue does not exist."
            else:
                room_val = int(room_raw)

        if not errors:
            try:
                db.update_exam(exam_id, ename, edate_raw, cid_val, room_val)
                flash(f"Examination '{ename}' (ID: {exam_id}) updated successfully.", "success")
                return redirect(url_for("examinations"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_exam.html",
            is_edit=True,
            action_url=url_for("edit_exam", exam_id=exam_id),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=exam_id,
            dropdown_courses=dropdown_courses,
            dropdown_classrooms=dropdown_classrooms,
            active_page="examinations"
        ), 400

    return render_template(
        "add_exam.html",
        is_edit=True,
        action_url=url_for("edit_exam", exam_id=exam_id),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=exam_id,
        dropdown_courses=dropdown_courses,
        dropdown_classrooms=dropdown_classrooms,
        active_page="examinations"
    )

@app.route("/examinations/<int:exam_id>/delete", methods=["POST"])
def delete_exam(exam_id):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("examinations"))
    try:
        db.delete_exam(exam_id)
        flash(f"Examination record #{exam_id} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("examinations"))


# --- 8. RESULT ---
@app.route("/results/<int:result_id>/edit", methods=["GET", "POST"])
def edit_result(result_id):
    rec = db.get_result_by_id(result_id)
    if not rec:
        flash(f"Result record with ID {result_id} does not exist.", "danger")
        return redirect(url_for("results"))

    errors = {}
    form_error = None
    dropdown_students = db.get_students_dropdown()
    dropdown_exams = db.get_exams_dropdown()
    form_data = {
        "result_id": str(rec["RESULT_ID"]),
        "grade": rec["GRADE"] or "",
        "marks": str(rec["MARKS"]) if rec["MARKS"] is not None else "",
        "sid": str(rec["SID"]) if rec["SID"] is not None else "",
        "exam_id": str(rec["EXAM_ID"]) if rec["EXAM_ID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_result.html",
                is_edit=True,
                action_url=url_for("edit_result", result_id=result_id),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=result_id,
                dropdown_students=dropdown_students,
                dropdown_exams=dropdown_exams,
                active_page="results"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        sid_raw = submitted.get("sid", "").strip()
        eid_raw = submitted.get("exam_id", "").strip()
        marks_raw = submitted.get("marks", "").strip()
        grade = submitted.get("grade", "").strip().upper()

        sid_val = None
        if not sid_raw:
            errors["sid"] = "Student selection is required."
        elif not sid_raw.isdigit() or int(sid_raw) <= 0:
            errors["sid"] = "Invalid student selection."
        elif not db.check_id_exists("STUDENT1143", "SID", int(sid_raw)):
            errors["sid"] = "Selected student does not exist."
        else:
            sid_val = int(sid_raw)

        eid_val = None
        if not eid_raw:
            errors["exam_id"] = "Examination selection is required."
        elif not eid_raw.isdigit() or int(eid_raw) <= 0:
            errors["exam_id"] = "Invalid examination selection."
        elif not db.check_id_exists("EXAM1143", "EXAM_ID", int(eid_raw)):
            errors["exam_id"] = "Selected examination does not exist."
        else:
            eid_val = int(eid_raw)

        marks_val = None
        if not marks_raw:
            errors["marks"] = "Marks obtained is required."
        else:
            try:
                marks_val = float(marks_raw)
                if marks_val < 0 or marks_val > 100:
                    errors["marks"] = "Marks must be between 0 and 100 (check constraint)."
            except ValueError:
                errors["marks"] = "Marks must be a numeric score."

        if not grade:
            errors["grade"] = "Letter grade is required."
        elif grade not in ("S", "A", "B", "C", "D", "E", "F"):
            errors["grade"] = "Grade must be S, A, B, C, D, E, or F."

        if not errors:
            try:
                db.update_result(result_id, grade, marks_val, sid_val, eid_val)
                flash(f"Exam Result #{result_id} (Grade: {grade}, Marks: {marks_val}) updated successfully.", "success")
                return redirect(url_for("results"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_result.html",
            is_edit=True,
            action_url=url_for("edit_result", result_id=result_id),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=result_id,
            dropdown_students=dropdown_students,
            dropdown_exams=dropdown_exams,
            active_page="results"
        ), 400

    return render_template(
        "add_result.html",
        is_edit=True,
        action_url=url_for("edit_result", result_id=result_id),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=result_id,
        dropdown_students=dropdown_students,
        dropdown_exams=dropdown_exams,
        active_page="results"
    )

@app.route("/results/<int:result_id>/delete", methods=["POST"])
def delete_result(result_id):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("results"))
    try:
        db.delete_result(result_id)
        flash(f"Result record #{result_id} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("results"))


# --- 9. LIBRARY ---
@app.route("/library/<int:book_id>/edit", methods=["GET", "POST"])
def edit_library(book_id):
    rec = db.get_library_by_id(book_id)
    if not rec:
        flash(f"Book record with ID {book_id} does not exist.", "danger")
        return redirect(url_for("library"))

    errors = {}
    form_error = None
    dropdown_universities = db.get_universities_dropdown()
    form_data = {
        "book_id": str(rec["BOOK_ID"]),
        "title": rec["TITLE"],
        "author": rec["AUTHOR"],
        "unid": str(rec["UNID"]) if rec["UNID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_library.html",
                is_edit=True,
                action_url=url_for("edit_library", book_id=book_id),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=book_id,
                dropdown_universities=dropdown_universities,
                active_page="library"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        title = submitted.get("title", "").strip()
        author = submitted.get("author", "").strip()
        unid_raw = submitted.get("unid", "").strip()

        if not title:
            errors["title"] = "Book title is required."
        elif len(title) > 100:
            errors["title"] = "Title cannot exceed 100 characters."

        if not author:
            errors["author"] = "Author name is required."
        elif len(author) > 100:
            errors["author"] = "Author cannot exceed 100 characters."

        unid_val = None
        if unid_raw:
            if not unid_raw.isdigit() or int(unid_raw) <= 0:
                errors["unid"] = "Invalid university selection."
            elif not db.check_id_exists("UNIVERSITY1143", "UNID", int(unid_raw)):
                errors["unid"] = "Selected university does not exist."
            else:
                unid_val = int(unid_raw)

        if not errors:
            try:
                db.update_library(book_id, title, author, unid_val)
                flash(f"Book '{title}' (ID: {book_id}) updated successfully.", "success")
                return redirect(url_for("library"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_library.html",
            is_edit=True,
            action_url=url_for("edit_library", book_id=book_id),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=book_id,
            dropdown_universities=dropdown_universities,
            active_page="library"
        ), 400

    return render_template(
        "add_library.html",
        is_edit=True,
        action_url=url_for("edit_library", book_id=book_id),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=book_id,
        dropdown_universities=dropdown_universities,
        active_page="library"
    )

@app.route("/library/<int:book_id>/delete", methods=["POST"])
def delete_library(book_id):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("library"))
    try:
        db.delete_library(book_id)
        flash(f"Book record #{book_id} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("library"))


# --- 10. HOSTEL ---
@app.route("/hostel/<int:hostel_id>/edit", methods=["GET", "POST"])
def edit_hostel(hostel_id):
    rec = db.get_hostel_by_id(hostel_id)
    if not rec:
        flash(f"Hostel record with ID {hostel_id} does not exist.", "danger")
        return redirect(url_for("hostel"))

    errors = {}
    form_error = None
    dropdown_universities = db.get_universities_dropdown()
    form_data = {
        "hostel_id": str(rec["HOSTEL_ID"]),
        "hostel_name": rec["HOSTEL_NAME"],
        "capacity": str(rec["CAPACITY"]) if rec["CAPACITY"] is not None else "",
        "unid": str(rec["UNID"]) if rec["UNID"] is not None else ""
    }

    if request.method == "POST":
        if not validate_csrf():
            return render_template(
                "add_hostel.html",
                is_edit=True,
                action_url=url_for("edit_hostel", hostel_id=hostel_id),
                errors={},
                form_error="Security verification failed (invalid CSRF token). Please try again.",
                form_data=request.form.to_dict(),
                suggested_id=hostel_id,
                dropdown_universities=dropdown_universities,
                active_page="hostel"
            ), 400

        submitted = request.form.to_dict()
        form_data.update(submitted)
        hname = submitted.get("hostel_name", "").strip()
        cap_raw = submitted.get("capacity", "").strip()
        unid_raw = submitted.get("unid", "").strip()

        if not hname:
            errors["hostel_name"] = "Hostel hall name is required."
        elif len(hname) > 100:
            errors["hostel_name"] = "Hostel name cannot exceed 100 characters."

        cap_val = None
        if not cap_raw:
            errors["capacity"] = "Resident capacity is required."
        elif not cap_raw.isdigit() or int(cap_raw) <= 0:
            errors["capacity"] = "Capacity must be greater than 0 (capacity > 0 constraint)."
        else:
            cap_val = int(cap_raw)

        unid_val = None
        if unid_raw:
            if not unid_raw.isdigit() or int(unid_raw) <= 0:
                errors["unid"] = "Invalid university selection."
            elif not db.check_id_exists("UNIVERSITY1143", "UNID", int(unid_raw)):
                errors["unid"] = "Selected university does not exist."
            else:
                unid_val = int(unid_raw)

        if not errors:
            try:
                db.update_hostel(hostel_id, hname, cap_val, unid_val)
                flash(f"Hostel '{hname}' (ID: {hostel_id}) updated successfully.", "success")
                return redirect(url_for("hostel"))
            except Exception as e:
                form_error = db.handle_db_write_error(e)

        return render_template(
            "add_hostel.html",
            is_edit=True,
            action_url=url_for("edit_hostel", hostel_id=hostel_id),
            errors=errors,
            form_error=form_error or ("Please correct the highlighted fields." if errors else None),
            form_data=form_data,
            suggested_id=hostel_id,
            dropdown_universities=dropdown_universities,
            active_page="hostel"
        ), 400

    return render_template(
        "add_hostel.html",
        is_edit=True,
        action_url=url_for("edit_hostel", hostel_id=hostel_id),
        errors={},
        form_error=None,
        form_data=form_data,
        suggested_id=hostel_id,
        dropdown_universities=dropdown_universities,
        active_page="hostel"
    )

@app.route("/hostel/<int:hostel_id>/delete", methods=["POST"])
def delete_hostel(hostel_id):
    if not validate_csrf():
        flash("Security verification failed (invalid CSRF token). Please try again.", "danger")
        return redirect(url_for("hostel"))
    try:
        db.delete_hostel(hostel_id)
        flash(f"Hostel record #{hostel_id} was deleted successfully.", "success")
    except Exception as e:
        flash(db.handle_db_write_error(e), "danger")
    return redirect(url_for("hostel"))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)



