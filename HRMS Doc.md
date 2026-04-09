#               **Hrms backend endpoints report** 

- ***Auth endpoints***   
    
  1\> auth/login   
  input:{  
    "email": "yash.infopulsetech@gmail.com"  
  }  
  output:{  
    "access\_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlZmUyZWE0NC1hMTU5LTQ0N2MtYTg5Yy1kM2JiY2Q2YjJmY2YiLCJleHAiOjE3NzU3MTc0MjksImlhdCI6MTc3NTcxMzgyOSwidHlwZSI6ImFjY2VzcyJ9.2jpnR3pwRwALTxc1lvZ\_sXVOnXpGRK-IvCVGWYYpzhU",  
    "refresh\_token": "4b27d509-73b6-45db-aa89-851e543cf747.daf95eb1-480e-4ed2-b573-6967d876dadc",  
    "token\_type": "bearer"  
  }  
    
  2\> auth/refresh  
  Input:{  
    "refresh\_token": "4b27d509-73b6-45db-aa89-851e543cf747.daf95eb1-480e-4ed2-b573-6967d876dadc"  
  }  
    
  output:{  
    "access\_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJlZmUyZWE0NC1hMTU5LTQ0N2MtYTg5Yy1kM2JiY2Q2YjJmY2YiLCJleHAiOjE3NzU3MTc1MTksImlhdCI6MTc3NTcxMzkxOSwidHlwZSI6ImFjY2VzcyJ9.X-piXyv\_TF6wg1VU3g5IqPmf2UjVS8bOkulLXOu-Hhg",  
    "refresh\_token": "4b27d509-73b6-45db-aa89-851e543cf747.daf95eb1-480e-4ed2-b573-6967d876dadc",  
    "token\_type": "bearer"  
  }  
    
    
  3\> auth/logout  
  Input:{  
    "refresh\_token": "4b27d509-73b6-45db-aa89-851e543cf747.daf95eb1-480e-4ed2-b573-6967d876dadc"  
  }  
  Output:{  
    "message": "Logged out"  
  }  
  




  4\> auth/me

  output:{

    "full\_name": "yash sakariya",

    "id": "efe2ea44-a159-447c-a89c-d3bbcd6b2fcf",

    "photo\_url": "nothing ",

    "role": "admin",

    "joined\_on": "2026-04-03",

    "created\_at": "2026-04-03T10:20:22.529203+00:00",

    "organization\_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",

    "department\_id": "a7a0bcab-a22f-4481-bf2e-05c16e34baee",

    "email": "yash.infopulsetech@gmail.com",

    "google\_id": null,

    "designation": "AI engineer",

    "is\_active": true,

    "last\_login\_at": "2026-04-09T05:50:29.741568+00:00",

    "updated\_at": "2026-04-03T10:20:22.529203+00:00"

  }

- ***Reporting endpoint***

            
1\>reporting/dropdown  
	Output:\[  
  {  
    "id": "26a8a7b8-c5e9-4362-9979-f296c44165f9",  
    "full\_name": "A.r. vaghela",  
    "designation": "full stack intern"  
  },  
  {  
    "id": "0f5acbbe-0b9c-4868-b0a6-4cb88b343d53",  
    "full\_name": "Shlok D Panchal",  
    "designation": "AI Engineer"  
  },  
  {  
    "id": "efe2ea44-a159-447c-a89c-d3bbcd6b2fcf",  
    "full\_name": "yash sakariya",  
    "designation": "AI engineer"  
  }  
\]

	2\>reporting{emp\_id}  
	Input:emp\_id \=  
	         Whole\_month \=true/false  
	Output:{  
  "avg\_hours\_this\_month": 0,  
  "records": \[  
    {  
      "date": "2026-04-08",  
      "tasks": "frontedn task ",  
      "check\_in\_at": "2026-04-08T08:49:12.404953Z",  
      "check\_out\_at": "2026-04-08T08:51:15.448029Z"  
    }  
  \]  
}

	3\>reporting{emp\_id}/csv  
	Input:emp\_id  
output:

| Response body Download file Response headers content-disposition: attachment; filename=report\_yash\_sakariya\_Apr\_2026.csv content-type: text/csv; charset=utf-8 date: Thu,09 Apr 2026 06:01:02 GMT server: uvicorn transfer-encoding: chunked |
| :---- |

- ***Employee endpoints***  
    
  1\>employee/add  
  Input:{  
    "email": "saif.infopulsetech@gmail.com",  
    "department\_id": "a7a0bcab-a22f-4481-bf2e-05c16e34baee",  
    "designation": "devops"  
  }  
  Output:{  
    "full\_name": null,  
    "id": "0fd4410e-e5d3-4bc0-a9bc-4ae5e56ab0ea",  
    "photo\_url": null,  
    "role": "employee",  
    "joined\_on": null,  
    "created\_at": "2026-04-09T06:15:41.900916+00:00",  
    "organization\_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",  
    "department\_id": "a7a0bcab-a22f-4481-bf2e-05c16e34baee",  
    "email": "saif.infopulsetech@gmail.com",  
    "google\_id": null,  
    "designation": "devops",  
    "is\_active": true,  
    "last\_login\_at": null,  
    "updated\_at": "2026-04-09T06:15:41.900916+00:00"  
  }  
    
    
  2\>employee/update-profile  
  Input:{  
    "full\_name": "yashsingh",  
    "photo\_url": "locally added "  
  }  
  Output:{  
    "message": "Profile updated"  
  }

  3\>employee/{emp\_id} (for remove remove soft delete)

  Input:emp\_id

  output:{

    "message": "Employee deactivated successfully"

  }


  4\>employee

  Output:


  

- ***Project endpoint***  
    
  1\>project/add  
  Input:{  
    "name": "flight booking app",  
    "description": "app for flight booking"  
  }  
  Output:{  
    "id": "90634328-6b41-44a7-a398-7304188013ef",  
    "name": "flight booking app",  
    "description": "app for flight booking",  
    "is\_active": true,  
    "created\_at": "2026-04-09T06:24:39.371702Z"  
  }

  2\>project/(for list)

  Output:\[

    {

      "id": "28ec9d11-13c4-45fc-9413-d80c34523199",

      "name": "hrmd backend",

      "description": "hr management system for the office",

      "is\_active": true,

      "created\_at": "2026-04-06T08:47:58.489128Z"

    },

    {

      "id": "90634328-6b41-44a7-a398-7304188013ef",

      "name": "flight booking app",

      "description": "app for flight booking",

      "is\_active": true,

      "created\_at": "2026-04-09T06:24:39.371702Z"

    }

  \]

  3\>project/{project\_id}

  Input:project\_id

  output:{

    "message": "Project deleted successfully"

  }


- ***Holiday endpoints***   
    
  1\>holiday/add  
  Input:{  
    "name": "gandhi jayanti",  
    "type": "public",  
    "date": "2026-04-20"  
  }  
  Output:{  
    "organization\_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",  
    "holiday\_date": "2026-04-20",  
    "holiday\_type": "public",  
    "name": "gandhi jayanti",  
    "id": "7b81434f-a54d-4f8f-ba3b-dc4b776307c1",  
    "created\_at": "2026-04-09T06:27:39.824018+00:00"  
  }  
    
  2\>holiday/ (for list holiday)  
  Output:\[  
   {  
      "organization\_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",  
      "holiday\_date": "2027-03-05",  
      "holiday\_type": "other",  
      "name": "wifi problem",  
      "id": "5fc38b6c-e787-488a-a05f-dfc33b531418",  
      "created\_at": "2026-04-06T11:29:57.531141+00:00"  
    },  
    {  
      "organization\_id": "e5a45018-c83d-4338-ba64-0e90e36a61c2",  
      "holiday\_date": "2026-04-20",  
      "holiday\_type": "public",  
      "name": "gandhi jayanti",  
      "id": "7b81434f-a54d-4f8f-ba3b-dc4b776307c1",  
      "created\_at": "2026-04-09T06:27:39.824018+00:00"  
    }  
  \]

  3\>holiday/{holiday\_id}

  Input:holiday\_id

  output:{

    "message": "Holiday deleted successfully"

  }


  


  


  


  

- ***Leave endpoints***   
    
  1\>leaves/me  
  Output:{  
    "current\_month": {  
      "month": 4,  
      "year": 2026,  
      "dates": \[  
        "2026-04-10"  
      \]  
    },  
    "previous\_months": \[\]  
  }  
    
    
  2\>leaves/summary  
  output:\[  
    {  
      "employee\_name": "yashsingh",  
      "casual\_balance": 1,  
      "casual\_used": 0,  
      "comp\_off\_balance": 0,  
      "comp\_off\_used": 0  
    },  
    {  
      "employee\_name": "Shlok D Panchal",  
      "casual\_balance": \-1,  
      "casual\_used": 2,  
      "comp\_off\_balance": 0,  
      "comp\_off\_used": 0  
    },  
    {  
      "employee\_name": "A.r. vaghela",  
      "casual\_balance": 1,  
      "casual\_used": 0,  
      "comp\_off\_balance": 0,  
      "comp\_off\_used": 0  
    }  
  \]


- ***Requests endpoints***   
    
  1\>requests/requests  
  Output:  
   {  
      "id": "8b855b88-f5ce-4d92-9626-5c44f695a716",  
      "request\_type": "comp\_off",  
      "from\_date": "2026-04-08",  
      "to\_date": "2026-04-08",  
      "reason": "anythign",  
      "status": "pending",  
      "linked\_session\_id": null,  
      "rejection\_note": null,  
      "reviewed\_at": null,  
      "created\_at": "2026-04-08T13:27:35.852672Z",  
      "employee\_id": "0f5acbbe-0b9c-4868-b0a6-4cb88b343d53",  
      "employee\_name": "Shlok D Panchal",  
      "employee\_email": "[shlok.infopulsetech@gmail.com](mailto:shlok.infopulsetech@gmail.com)"

  },

2\>requests/{req\_id}/approve  
Input: req\_id  
output:{  
  "id": "8b855b88-f5ce-4d92-9626-5c44f695a716",  
  "request\_type": "comp\_off",  
  "from\_date": "2026-04-08",  
  "to\_date": "2026-04-08",  
  "reason": "anythign",  
  "status": "approved",  
  "linked\_session\_id": null,  
  "rejection\_note": null,  
  "reviewed\_at": "2026-04-09T06:52:03.499766Z",  
  "created\_at": "2026-04-08T13:27:35.852672Z"  
}

3\>requests/{req\_id}/reject  
Input: req\_id  
output:{  
  "id": "2eb6a48b-df13-4f8d-a92d-e39a5d947a3c",  
  "request\_type": "leave",  
  "from\_date": "2026-04-08",  
  "to\_date": "2026-04-08",  
  "reason": "nothing",  
  "status": "rejected",  
  "linked\_session\_id": null,  
  "rejection\_note": "due to work load",  
  "reviewed\_at": "2026-04-09T07:00:17.967209Z",  
  "created\_at": "2026-04-08T09:03:57.972746Z"  
}

4\>requests (get requests)  
Output:\[  
  {  
    "id": "8b855b88-f5ce-4d92-9626-5c44f695a716",  
    "request\_type": "comp\_off",  
    "from\_date": "2026-04-08",  
    "to\_date": "2026-04-08",  
    "reason": "anythign",  
    "status": "approved",  
    "linked\_session\_id": null,  
    "rejection\_note": null,  
    "reviewed\_at": "2026-04-09T06:52:03.499766Z",  
    "created\_at": "2026-04-08T13:27:35.852672Z"  
  },  
  {  
    "id": "c1b5e971-382a-45d8-b1e7-03623439ff59",  
    "request\_type": "leave",  
    "from\_date": "2026-04-10",  
    "to\_date": "2026-04-10",  
    "reason": "string",  
    "status": "approved",  
    "linked\_session\_id": null,  
    "rejection\_note": null,  
    "reviewed\_at": "2026-04-08T13:14:22.125516Z",  
    "created\_at": "2026-04-08T11:43:17.303827Z"  
  }  
\]

5\>requests/ (create)  
Input:{  
  "request\_type": "wfh",  
  "from\_date": "2026-04-15",  
  "to\_date": "2026-04-15",  
  "reason": "sick"  
}

Output:{  
  "id": "8306a98c-4d18-417b-972b-7f5f001ee100",  
  "request\_type": "wfh",  
  "from\_date": "2026-04-15",  
  "to\_date": "2026-04-15",  
  "reason": "sick",  
  "status": "pending",  
  "linked\_session\_id": null,  
  "rejection\_note": null,  
  "reviewed\_at": null,  
  "created\_at": "2026-04-09T07:39:50.262580Z"  
}

6\>requests/{reu\_id} (delete)  
Input:req\_id  
Output:request deleted

- ***Attendance endpoint***   
    
  1\> attendace/check-in  
  Input:{  
    "tasks": \[  
      {  
        "project\_id": "28ec9d11-13c4-45fc-9413-d80c34523199",  
        "description": "tasks",  
        "hours": 2  
      }  
    \]  
  }  
  Output:{  
    "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",  
    "session\_date": "2026-04-09",  
    "check\_in\_at": "2026-04-09T07:20:59.272108Z",  
    "check\_out\_at": null,  
    "total\_hours": null,  
    "work\_mode": "office",  
    "is\_corrected": false,  
    "tasks": \[  
      {  
        "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",  
        "project\_id": "28ec9d11-13c4-45fc-9413-d80c34523199",  
        "description": "tasks",  
        "hours": 2  
      }  
    \]  
  }  
    
    
  2\> attendance/today  
  Output:{  
    "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",  
    "session\_date": "2026-04-09",  
    "check\_in\_at": "2026-04-09T07:20:59.272108Z",  
    "check\_out\_at": null,  
    "total\_hours": null,  
    "work\_mode": "office",  
    "is\_corrected": false,  
    "tasks": \[  
      {  
        "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",  
        "project\_id": "28ec9d11-13c4-45fc-9413-d80c34523199",  
        "description": "tasks",  
        "hours": 2  
      }  
    \]  
  }  
    
    
  3\> attendance/check-out  
  Output:{  
    "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",  
    "session\_date": "2026-04-09",  
    "check\_in\_at": "2026-04-09T07:20:59.272108Z",  
    "check\_out\_at": "2026-04-09T07:44:49.158141Z",  
    "total\_hours": 0.4,  
    "work\_mode": "office",  
    "is\_corrected": false,  
    "tasks": \[\]  
  }  
    
    
  4\>attendance/avg-hours  
  Output:{  
    "avg\_hours": 0.4  
  }  
    
    
  5\>attendance/sessions/download  
  Input:month , year

Output:

| Response body Download file Response headers content-disposition: attachment; filename="attendance\_april\_2026.csv" content-type: text/csv; charset=utf-8 date: Thu,09 Apr 2026 07:45:26 GMT server: uvicorn transfer-encoding: chunked |
| :---- |

6\> attendance/sessions  
Output:\[  
  {  
    "id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",  
    "session\_date": "2026-04-09",  
    "check\_in\_at": "2026-04-09T07:20:59.272108Z",  
    "check\_out\_at": null,  
    "total\_hours": null,  
    "work\_mode": "office",  
    "is\_corrected": false,  
    "tasks": \[  
      {  
        "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",  
        "description": "tasks",  
        "hours\_logged": 2,  
        "project\_id": "28ec9d11-13c4-45fc-9413-d80c34523199",  
        "project\_name": "hrmd backend"  
      }  
    \],  
    "tasks\_summary": "tasks"  
  },  
  {  
    "id": "96a38504-2ad1-4a37-add0-a54bbb36fee7",  
    "session\_date": "2026-04-08",  
    "check\_in\_at": "2026-04-08T13:23:05.824268Z",  
    "check\_out\_at": null,  
    "total\_hours": null,  
    "work\_mode": "office",  
    "is\_corrected": false,  
    "tasks": \[  
      {  
        "id": "be7bdb21-b190-433a-abd9-c735929e41d4",  
        "description": "string",  
        "hours\_logged": 2,  
        "project\_id": "28ec9d11-13c4-45fc-9413-d80c34523199",  
        "project\_name": "hrmd backend"  
      }  
    \],  
    "tasks\_summary": "string"  
  }  
\]

- ***Task endpoints***   
    
  1\>tasks/today  
  Output:\[  
    {  
      "id": "45a45fee-3b2d-44b1-816c-de05f6f633bc",  
      "session\_id": "5b132df2-2d15-40dc-a5ac-0f1de31cc2e9",  
      "project\_id": "28ec9d11-13c4-45fc-9413-d80c34523199",  
      "description": "tasks",  
      "hours\_logged": 2,  
      "sort\_order": 0  
    }  
  \]  
    
    
  2\>tasks  
  Input:{  
    "project\_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  
    "description": "string",  
    "hours": 0  
  }  
    
  Output:{  
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  
    "session\_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  
    "project\_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",  
    "description": "string",  
    "hours\_logged": 0,  
    "sort\_order": 0  
  }  
    
    
  3\>tasks/{task\_id}  
  Input:task\_id  
  Output:task\_deleted  
    
- ***Leave balance endpoint***  
    
  1\>balance/me   
  output:\[  
    {  
      "leave\_type": "casual",  
      "year": 2026,  
      "month": 4,  
      "opening\_balance": 0,  
      "accrued": 1,  
      "used": 2,  
      "adjusted": 0,  
      "closing\_balance": \-1  
    },  
    {  
      "leave\_type": "comp\_off",  
      "year": 2026,  
      "month": 4,  
      "opening\_balance": 0,  
      "accrued": 1,  
      "used": 0,  
      "adjusted": 0,  
      "closing\_balance": 1  
    }  
  \]  
    
- ***Calendar endpoints***   
  1\>calendar  
  input:{  
    "month": 4,  
    "year": 2026,  
    "data": {  
      "2026-04-10": \[  
        {  
          "employee\_name": "Shlok D Panchal",  
          "type": "leave"  
        }  
      \]  
    }  
  }  
    
  